import numpy as np


async def check_output(fixture, symbol, expected):
    await fixture.write(symbol, np.full(expected.nbytes, 0xa5, dtype=np.uint8))
    await fixture.run_to_halt(timeout_cycles=100000)
    assert not fixture.fault()
    data = await fixture.read(symbol, expected.nbytes)
    np.testing.assert_array_equal(
        data.view(expected.dtype).reshape(expected.shape), expected
    )


async def float_add(fixture, elf):
    await fixture.load_elf_and_lookup_symbols(
        elf, ["input1", "input2", "output"]
    )
    a = np.arange(-4, 4, dtype=np.float32)
    b = np.arange(8, dtype=np.float32) * 0.25
    await fixture.write("input1", a)
    await fixture.write("input2", b)
    await check_output(fixture, "output", a + b)


async def vector_add(fixture, elf):
    await fixture.load_elf_and_lookup_symbols(elf, ["output"])
    await check_output(fixture, "output", np.full(1024, 7, dtype=np.int16))


async def matrix_multiply(fixture, elf):
    await fixture.load_elf_and_lookup_symbols(
        elf, [
            "mm_a", "mm_b", "mm_tm", "mm_tn", "mm_tk", "mm_init_mode",
            "mm_impl", "vtmms_mt0", "mm_out"
        ]
    )
    a = np.arange(-32, 32, dtype=np.int8).reshape(4, 16)
    b = np.arange(64, dtype=np.uint8).reshape(4, 16)
    await fixture.write("mm_a", a.ravel())
    await fixture.write("mm_b", b.ravel())
    await fixture.write_word("mm_tm", 16)
    await fixture.write_word("mm_tn", 16)
    await fixture.write_word("mm_tk", 3)
    await fixture.write_word("mm_init_mode", 0)
    await fixture.write_ptr("mm_impl", "vtmms_mt0")
    expected = a[:3].astype(np.int32).T @ b[:3].astype(np.int32)
    await check_output(fixture, "mm_out", expected)
