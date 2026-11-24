import argparse
import asyncio
from contextlib import contextmanager
import ctypes
import fcntl
import mmap
import os
from pathlib import Path
import struct
import time

from elftools.elf.elffile import ELFFile
import numpy as np

import workloads

BAR_OFFSET = 0x100000
DESIGN_ID = 0x434E5032
CSR = 0x30000


class Board:

    def __init__(self, window, timeout):
        self.window = window
        self.timeout = timeout
        if self.word(0x40000) != DESIGN_ID:
            raise RuntimeError(
                "PF1 BAR2 does not identify the CoralNPU V80 design"
            )

    def word(self, addr):
        return ctypes.c_uint32.from_buffer(self.window, addr).value

    def put_word(self, addr, value):
        ctypes.c_uint32.from_buffer(self.window, addr).value = value

    def store(self, addr, data):
        if not data:
            return
        end = addr + len(data)
        if not (0 <= addr < end <= 0x2000 or 0x10000 <= addr < end <= 0x18000):
            raise ValueError(f"Write outside TCM at {addr:#x}..{end:#x}")
        for base in range(addr & ~3, end, 4):
            lo, hi = max(base, addr), min(base + 4, end)
            if hi - lo == 4:
                value, = struct.unpack_from("<I", data, base - addr)
            else:
                partial = bytearray(self.word(base).to_bytes(4, "little"))
                partial[lo - base:hi - base] = data[lo - addr:hi - addr]
                value = int.from_bytes(partial, "little")
            self.put_word(base, value)

    async def load_elf_and_lookup_symbols(self, path, symbols):
        with open(path, "rb") as f:
            elf = ELFFile(f)
            if elf.elfclass != 32 or elf[
                    "e_machine"] != "EM_RISCV" or not elf.little_endian:
                raise ValueError(f"Expected a little-endian RV32 ELF: {path}")
            self.entry = elf["e_entry"]
            if not 0 <= self.entry < 0x2000 or self.entry % 4:
                raise ValueError(f"Invalid ITCM entry {self.entry:#x}")
            table = elf.get_section_by_name(".symtab")
            self.symbols = {
                name: table.get_symbol_by_name(name)[0]["st_value"]
                for name in symbols
            }
            self.reset_core()
            for segment in elf.iter_segments("PT_LOAD"):
                data = segment.data()
                size = segment["p_memsz"]
                if not len(data) <= size <= 32768:
                    raise ValueError(f"Invalid load segment in {path}")
                self.store(segment["p_paddr"], data.ljust(size, b"\0"))

    async def write(self, symbol, values):
        self.store(
            self.symbols[symbol],
            np.ascontiguousarray(values).tobytes()
        )

    async def write_word(self, symbol, value):
        self.store(self.symbols[symbol], struct.pack("<I", value))

    async def write_ptr(self, destination, source):
        await self.write_word(destination, self.symbols[source])

    async def read(self, symbol, size):
        addr = self.symbols[symbol]
        if addr % 4 or size % 4 or not 0x10000 <= addr <= 0x18000 - size:
            raise ValueError("Expected an aligned DTCM result")
        words = [self.word(addr + i) for i in range(0, size, 4)]
        return np.asarray(words, dtype="<u4").view(np.uint8)

    def reset_core(self):
        self.put_word(CSR, 1)
        if self.word(CSR) != 1:
            raise RuntimeError("Core reset did not assert")

    def fault(self):
        return bool(self.word(CSR + 8) & 2)

    async def run_to_halt(self, timeout_cycles):
        self.reset_core()
        self.put_word(CSR + 4, self.entry)
        if self.word(CSR + 4) != self.entry or self.word(CSR + 8) & 3:
            raise RuntimeError("Core did not reach its reset state")
        self.put_word(CSR, 0)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            status = self.word(CSR + 8)
            if status & 2:
                raise RuntimeError(f"Core fault at entry {self.entry:#x}")
            if status & 1:
                return
            await asyncio.sleep(0.001)
        raise TimeoutError(f"Core did not halt within {self.timeout}s")


async def run(board, directory):
    for repetition in range(2):
        for check, filename in [
            (workloads.float_add, "coralnpu_v2_hello_world_add_floats.elf"),
            (workloads.vector_add, "coralnpu_v2_rvv_add_intrinsic.elf"),
            (workloads.matrix_multiply, "vme_matmul_test.elf"),
        ]:
            await check(board, directory / filename)
            print(f"PASS {repetition + 1} {check.__name__}", flush=True)


@contextmanager
def open_board(bdf, timeout):
    device = Path("/sys/bus/pci/devices") / bdf
    if device.joinpath("device").read_text().strip(
    ) != "0x50b5" or device.joinpath("vendor").read_text().strip() != "0x10ee":
        raise SystemExit("Expected the Alveo V80 user PCI function")
    fd = os.open(device / "resource2", os.O_RDWR | os.O_SYNC)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with mmap.mmap(fd, 0x41000, offset=BAR_OFFSET) as window:
            yield Board(window, timeout)
    finally:
        os.close(fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True, help="PF1 PCI BDF")
    parser.add_argument("--elf-dir", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=3)
    args = parser.parse_args()
    with open_board(args.device, args.timeout) as board:
        asyncio.run(run(board, args.elf_dir))
