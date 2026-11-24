load("@rules_python//python:defs.bzl", "py_library")
load("//rules:coco_tb.bzl", "verilator_cocotb_model")
load("//rules:coralflow_test.bzl", "coralflow_test")
load("//tests/cocotb:build_defs.bzl", "VERILATOR_BUILD_ARGS")

py_library(
    name = "workloads",
    srcs = ["workloads.py"],
)

verilator_cocotb_model(
    name = "v80_core_model",
    cflags = VERILATOR_BUILD_ARGS + [
        "-DFPGA_XILINX",
        "-DFPGA_VERSAL_HBM",
        "-DZVT_ON",
        "-DZVTBF16FMM_ON",
        "-DZVTI16I32MM_ON",
    ],
    hdl_toplevel = "VmeCoreMiniAxi",
    trace = False,
    verilog_source = "//hdl/chisel/src/coralnpu/prod:VmeCoreMiniAxi.sv",
    verilog_sources = ["bufgce_sim.sv"],
    deps = ["//hdl/verilog:sram_backdoor"],
)

coralflow_test(
    name = "v80_smoke",
    size = "large",
    srcs = ["v80_smoke.py"],
    data = [
        "//examples:coralnpu_v2_hello_world_add_floats.elf",
        "//examples:coralnpu_v2_rvv_add_intrinsic.elf",
        "//tests/cocotb/vme_test:vme_matmul_test",
    ],
    hdl_toplevel = "VmeCoreMiniAxi",
    targets = ["verilator"],
    testcases = [
        "float_add",
        "vector_add",
        "matrix_multiply",
    ],
    verilator_model = ":v80_core_model",
    deps = [
        ":workloads",
        "@bazel_tools//tools/python/runfiles",
    ],
)

coralflow_test(
    name = "lm_check",
    size = "large",
    srcs = ["lm_check.py"],
    data = [
        "//fpga/v80/lm:decoder.elf",
        "//fpga/v80/lm:stories.bin",
    ],
    hdl_toplevel = "VmeCoreMiniAxi",
    targets = ["verilator"],
    testcases = ["generation"],
    verilator_model = ":v80_core_model",
    deps = [
        "//fpga/v80/lm:inference",
        "@bazel_tools//tools/python/runfiles",
    ],
)
