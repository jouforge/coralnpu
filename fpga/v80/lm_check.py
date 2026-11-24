from pathlib import Path

from bazel_tools.tools.python.runfiles import runfiles
from coralnpu_test_utils.coralflow.runner import coralflow_test
from fpga.v80.lm.inference import generate, load
from fpga.v80.lm.model import Reference


@coralflow_test
async def generation(fixture):
    files = runfiles.Create()
    root = "coralnpu_hw/fpga/v80/lm/"
    blob = Path(files.Rlocation(root + "stories.bin")).read_bytes()
    await load(fixture, files.Rlocation(root + "decoder.elf"), blob)
    reference = Reference(blob)
    for prompt, count in [("Once", 4), ("a", 2),
                          ("Once upon a time there was a", 3)]:
        tokens, cycles, _ = await generate(fixture, prompt, count, reference)
        print(
            f"Verified {prompt!r}: ids={tokens}, first token after {cycles[0]} cycles",
            flush=True
        )
