# CoralNPU on AMD Alveo V80

The AMR V80 platform exposes the production `VmeCoreMiniAxi` through
PF1 BAR2. The core runs at 25 MHz and executes programs from local TCM.
Its external AXI master returns DECERR for accesses outside the local map.
The AMR management function and PF1 GPIO keep their base-platform addresses.

| PF1 BAR2 offset | Size | Function |
| --- | --- | --- |
| `0x020000` | 4 KiB | AMR PF1 GPIO |
| `0x100000` | 8 KiB | ITCM |
| `0x110000` | 32 KiB | DTCM |
| `0x130000` | 12 bytes | Control, start PC, status (32-bit registers) |
| `0x140000` | 4 bytes | Design ID, `0x434e5032` |

## Build the core and run the reference workloads

From the repository root, use Bazel 9.1.0 with Clang and LLD 19 on PATH.

```sh
bazel build --action_env=PATH --host_action_env=PATH --repo_env=PATH \
  //hdl/chisel/src/coralnpu/prod:VmeCoreMiniAxi.sv \
  //examples:coralnpu_v2_hello_world_add_floats.elf \
  //examples:coralnpu_v2_rvv_add_intrinsic.elf \
  //tests/cocotb/vme_test:vme_matmul_test.elf

bazel test --action_env=PATH --host_action_env=PATH --repo_env=PATH \
  --test_env=COCOTB_USE_FRONTDOOR=1 --test_output=errors \
  //fpga/v80:v80_smoke_verilator
```

The simulation uses the FPGA matrix datapath and a behavioral BUFGCE clock
gate. It loads each ELF over AXI, checks halt and fault status and
compares every output with a host reference. The workloads cover scalar
floating-point addition, 1,024 RVV elements and a 16 × 16 integer matrix result.

## Build the device images

Use Vivado and Vitis 2026.1.1 with the V80 part and board files. On the build
host, set `BOARD_SRC` to the absolute path of this directory, `RTL` to
the generated monolithic `VmeCoreMiniAxi.sv`, and `WORK` to a private build
directory. The AMR platform sources below are from `amr_vivado_designs`
revision `4b7d244`. The AMC firmware sources are from AMR revision `c21a01b`.

```sh
AMR="$HOME/workspace/amr"
PLATFORM="$AMR/build_v80/amr_vivado_designs/alveo_v80/platforms/v80_base"
mkdir -p "$WORK"
cd "$WORK"
vivado -mode batch -source "$BOARD_SRC/build.tcl" \
  -tclargs "$PLATFORM" "$RTL" "$WORK/design"

git clone --no-hardlinks "$AMR" "$WORK/amr-fw"
git -C "$WORK/amr-fw" checkout --detach c21a01b
source /opt/Xilinx/2026.1.1/Vitis/settings64.sh
mkdir -p "$WORK/firmware"
cd "$WORK/firmware"
"$WORK/amr-fw/fw/AMC/scripts/build.sh" -xsa "$WORK/design/coral_v80.xsa" -profile v80
sha256sum build_amc/amr_ospi.bin "$WORK/design/coral_v80_pld.pdi"
```

Keep the routed timing, CDC, DRC and utilization reports with the XSA and
both image hashes. The JTAG boot image is `firmware/build_amc/amr_ospi.bin`
and the matching PL segment is `design/coral_v80_pld.pdi`.

For the 25 MHz build on `qfpga0`, Vivado routed all 839,149 routable nets.
Worst setup slack was +0.007 ns and worst hold slack was +0.011 ns.
All 377 CDC endpoints were classified safe. The DRC report contained 4,259
warnings and zero errors or critical warnings. The timing report identifies
56 constant-clock endpoints in the PCIe transceiver IP and the two
asynchronous SMBus pins without external delay constraints.

## Load and verify on the shared card

Reserve the V80 with its current user and agree on the image to leave loaded.
Record the target cable serial, both PCI functions, their drivers, their parent
bridge and the queue configuration. An `ami_tool overview` result of
`NO_AMC` can occur while another image is running and does not indicate
availability. Quiesce clients and queues and have the host administrator
remove both PCI functions before volatile JTAG programming.

```sh
vivado -mode batch -source "$BOARD_SRC/program.tcl" \
  -tclargs "$HW_SERVER" "$CABLE_SERIAL" \
  "$WORK/firmware/build_amc/amr_ospi.bin" "$WORK/design/coral_v80_pld.pdi"
```

Rescan the saved parent bridge, verify both PCI functions and wait for AMC
READY. Give the test process read/write access to the selected PF1
`resource2`. Set `ELF_DIR` to the directory containing the three ELF files
built above. The host runner requires Python 3, NumPy and pyelftools.

```sh
python3 "$BOARD_SRC/run_board.py" --device "$PF1_BDF" --elf-dir "$ELF_DIR"
```

The runner checks the design ID, loads each workload, starts the core and
checks the results twice. Record all six PASS lines and the programming and
management logs. Return the card to the agreed image and driver state.

On 2026-11-24, both JTAG transfers on `qfpga0` reported DONE. AMC 3.1.0
reached READY and QDMA queue 4 returned online in both directions. The host
ran all three workloads twice through PF1 BAR2 at `0000:41:00.1`. All six
result comparisons passed.

For character-level Transformer inference, see the [language model guide](lm/README.md).
