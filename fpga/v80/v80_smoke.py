from bazel_tools.tools.python.runfiles import runfiles
from coralnpu_test_utils.coralflow.runner import coralflow_test
from fpga.v80 import workloads


@coralflow_test
async def float_add(fixture):
    elf = runfiles.Create(
    ).Rlocation("coralnpu_hw/examples/coralnpu_v2_hello_world_add_floats.elf")
    await workloads.float_add(fixture, elf)


@coralflow_test
async def vector_add(fixture):
    elf = runfiles.Create(
    ).Rlocation("coralnpu_hw/examples/coralnpu_v2_rvv_add_intrinsic.elf")
    await workloads.vector_add(fixture, elf)


@coralflow_test
async def matrix_multiply(fixture):
    elf = runfiles.Create(
    ).Rlocation("coralnpu_hw/tests/cocotb/vme_test/vme_matmul_test.elf")
    await workloads.matrix_multiply(fixture, elf)
