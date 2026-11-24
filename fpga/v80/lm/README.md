# Character Transformer on V80

The 25 MHz V80 image runs a one-block, one-head causal decoder with 32
channels, a 64-channel ReLU feed-forward layer, learned positions, and tied
input/output embeddings. The core computes RMS normalization, attention,
residuals, logits and greedy selection. Each request starts with a fresh KV
cache. The ELF and exported weights remain loaded between requests.

## Generate text

Build from the repository root using the [V80 toolchain](../README.md).

```sh
bazel build --action_env=PATH --host_action_env=PATH --repo_env=PATH \
  //fpga/v80/lm:decoder.elf
bazel cquery //fpga/v80/lm:decoder.elf --output=files
```

On the host with the CoralNPU image loaded, set `ELF` to the resulting file.
The host needs NumPy, pyelftools and access to PF1 BAR2. Repeat `--prompt` to
run multiple requests after one load.

```sh
python3 fpga/v80/generate_text.py --device 0000:41:00.1 --elf "$ELF" \
  --prompt 'Once upon a' --prompt 'Lily' --new-tokens 12 --verify
```

The limit is 32 positions including BOS, prompt and generated characters.
Generation stops at EOS or the requested length. The 64-symbol vocabulary
includes uppercase and lowercase ASCII letters, selected punctuation,
whitespace, BOS, EOS and an unknown symbol. Verification checks all 64
integer logits at every evaluated position, including prefill, against the
host reference. First-token and decode timings use the on-core cycle counter.
End-to-end throughput includes writing the request, starting and polling the
core, and reading generated IDs. The CLI reports load time separately and excludes reference checks from throughput.

## Reproduce training and export

Use Python 3.12 with PyTorch 2.9.0 (CPU) and NumPy 2.5.4. Training reads the
first 2 MiB of each official text split, verifies their SHA-256 hashes and
keeps complete stories. The script fixes the dataset revision, sampling seed
and 3,000 AdamW steps. Validation compares all three models on the same 128
held-out windows of 32 predictions. The corpus is available from the
[TinyStories dataset](https://huggingface.co/datasets/roneneldan/TinyStories).

```sh
python3 fpga/v80/lm/train.py --cache "$HOME/.cache/coral-lm" \
  --output /tmp/stories.bin
cmp /tmp/stories.bin fpga/v80/lm/stories.bin
```

The 11,776-byte export contains six row-major INT8 arrays in model order
(embedding, position, QKV, attention output, FFN up, FFN down) and 256
little-endian uint16 exponential lookup values. Weights use a scale of 1/128
and activations use 1/32. RVV projections multiply signed bytes and reduce
into int32. The final logits use a scale of 3/4096. The integer reference
implements the same rounding, saturation and first-maximum tie break.

## Verify the RTL

```sh
bazel test --action_env=PATH --host_action_env=PATH --repo_env=PATH \
  --test_env=COCOTB_USE_FRONTDOOR=1 --test_output=errors \
  //fpga/v80:lm_check_verilator
```

The test uses the FPGA datapath in Verilator. It loads the ELF and weights
once and checks three requests, including the 32-position boundary.

## Measured results

Two CPU training runs produced identical exports with SHA-256
`0a772fb73e5a0cdb3b2fe4db1c9087f53df18ba41df7759bc7bd40e0a3091d87`.
Validation loss in nats per token was 3.06535 for the unigram baseline,
1.62828 for PyTorch and 1.65630 for the integer decoder. Given
`Once upon a`, 12 greedy steps produced `Once upon a time to sai` in
PyTorch and `Once upon and the was a` after quantization.

The ELF used 2,672 bytes of ITCM. DTCM contained 11,840 bytes of initialized
data and 10,440 bytes of BSS, including the 2,048-byte KV cache and
8,192-byte logit trace. The linker reserved a 2,048-byte stack and assigned
the remaining aligned space to the heap (8,432 bytes). Inference uses static
buffers and stack storage.

On the 25 MHz V80 in qfpga0, five requests over two loads passed the
per-position logit and token checks. The first load served `Once upon a`,
`Lily` and then `Once upon a` again. The repeated request produced identical
token IDs and core cycle counts. Another request used all 32 positions.

| Prompt | New characters | Core first token | Subsequent cycles/token (min–max) | End-to-end tokens/s |
| --- | ---: | ---: | ---: | ---: |
| Once upon a | 12 | 9.431 ms | 23,083–27,026 | 557 |
| Lily | 12 | 3.682 ms | 20,442–24,240 | 852 |
| Once upon a time there was a | 3 | 26.574 ms | 29,684–30,141 | 100 |

The first load took 19.96 ms. Each throughput value is a single host-wall-clock
measurement with that prompt, including prefill and excluding model loading.
