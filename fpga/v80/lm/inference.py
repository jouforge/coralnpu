import time

import numpy as np

from .model import MODEL_BYTES, encode

SYMBOLS = [
    "weights", "ids", "prompt_len", "new_tokens", "produced", "elapsed_cycles",
    "logits", "_ret"
]


async def load(fixture, elf, weights):
    if len(weights) != MODEL_BYTES:
        raise ValueError("Unexpected weights size")
    await fixture.load_elf_and_lookup_symbols(elf, SYMBOLS)
    await fixture.write("weights", np.frombuffer(weights, np.uint8))


async def generate(fixture, prompt, count, reference=None):
    tokens = encode(prompt)
    if count < 1 or len(tokens) + count > 32:
        raise ValueError("BOS + prompt + new tokens must fit in 32 positions")
    start = time.perf_counter()
    await fixture.write("ids", np.asarray(tokens, dtype=np.uint8))
    await fixture.write_word("prompt_len", len(tokens))
    await fixture.write_word("new_tokens", count)
    await fixture.run_to_halt(timeout_cycles=5000000)
    if fixture.fault() or int.from_bytes(await fixture.read("_ret", 4),
                                         "little") != 0:
        raise RuntimeError("Decoder failed")
    size = int.from_bytes(await fixture.read("produced", 4), "little")
    if not 1 <= size <= count:
        raise RuntimeError(f"Unexpected output length {size}")
    output = (await fixture.read("ids",
                                 32))[len(tokens):len(tokens) + size].tolist()
    end = time.perf_counter()
    cycles = (await fixture.read("elapsed_cycles", size * 4)).view("<u4")
    if reference is not None:
        expected, scores = reference.generate(tokens, count)
        np.testing.assert_array_equal(output, expected)
        data = await fixture.read("logits", scores.size * 4)
        np.testing.assert_array_equal(
            data.view("<i4").reshape(scores.shape), scores
        )
    return output, cycles, end - start
