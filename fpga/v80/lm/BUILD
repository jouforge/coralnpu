load("@rules_python//python:defs.bzl", "py_library")
load("//rules:coralnpu_v2.bzl", "coralnpu_v2_binary")

package(default_visibility = ["//fpga/v80:__pkg__"])

coralnpu_v2_binary(
    name = "decoder",
    srcs = ["decoder.cc"],
    copts = [
        "-Os",
        "-fno-tree-vectorize",
    ],
    stack_size_bytes = 2048,
)

exports_files(["stories.bin"])

py_library(
    name = "inference",
    srcs = [
        "inference.py",
        "model.py",
    ],
)
