#include <riscv_vector.h>
#include <stdint.h>

struct Weights {
  int8_t embed[64][32], position[32][32], qkv[96][32], out[32][32];
  int8_t up[64][32], down[32][64];
  uint16_t exp_table[256];
};

extern "C" {
alignas(16) Weights weights __attribute__((section(".data"))) = {};
alignas(16) uint8_t ids[32] __attribute__((section(".data"))) = {};
uint32_t prompt_len __attribute__((section(".data")))         = 1;
uint32_t new_tokens __attribute__((section(".data")))         = 1;
volatile uint32_t produced;
uint32_t elapsed_cycles[32];
int32_t logits[32][64];
}
static int8_t keys[32][32], values[32][32];

static int8_t clip(int x) { return x < -128 ? -128 : x > 127 ? 127 : x; }

static uint32_t cycles() {
  uint32_t n;
  asm volatile("csrr %0, mcycle" : "=r"(n)::"memory");
  return n;
}

static int dot(const int8_t *a, const int8_t *b, unsigned n) {
  auto x    = __riscv_vle8_v_i8m4(a, n);
  auto y    = __riscv_vle8_v_i8m4(b, n);
  auto xy   = __riscv_vwmul_vv_i16m8(x, y, n);
  auto zero = __riscv_vmv_v_x_i32m1(0, 1);
  return __riscv_vmv_x_s_i32m1_i32(__riscv_vwredsum_vs_i16m8_i32m1(xy, zero, n));
}

template <unsigned Rows, unsigned Cols>
static void project(int8_t *dst, const int8_t (&w)[Rows][Cols], const int8_t *src) {
  for (unsigned i = 0; i < Rows; ++i)
    dst[i] = clip((dot(w[i], src, Cols) + 64) >> 7);
}

static void normalize(int8_t *dst, const int8_t *x) {
  int mean = dot(x, x, 32) / 32 + 1;
  int root = 0;
  for (int bit = 128; bit; bit >>= 1) {
    int next = root + bit;
    if (next * next <= mean)
      root = next;
  }
  for (int i = 0; i < 32; ++i)
    dst[i] = clip(x[i] * 32 / root);
}

static void forward(unsigned pos) {
  alignas(16) int8_t x[32], normalized[32], qkv[96], ctx[32], tmp[32], hidden[64];
  int score[32], prob[32];
  for (int i = 0; i < 32; ++i)
    x[i] = clip(weights.embed[ids[pos]][i] + weights.position[pos][i]);
  normalize(normalized, x);
  project(qkv, weights.qkv, normalized);
  for (int i = 0; i < 32; ++i) {
    keys[pos][i]   = qkv[i + 32];
    values[pos][i] = qkv[i + 64];
  }
  int peak = INT32_MIN;
  for (unsigned t = 0; t <= pos; ++t) {
    score[t] = dot(qkv, keys[t], 32) / 362;
    if (score[t] > peak)
      peak = score[t];
  }
  int sum = 0;
  for (unsigned t = 0; t <= pos; ++t) {
    int diff = peak - score[t];
    prob[t]  = weights.exp_table[diff < 255 ? diff : 255];
    sum += prob[t];
  }
  for (int i = 0; i < 32; ++i) {
    int acc = 0;
    for (unsigned t = 0; t <= pos; ++t)
      acc += prob[t] * values[t][i];
    ctx[i] = acc / sum;
  }
  project(tmp, weights.out, ctx);
  for (int i = 0; i < 32; ++i)
    x[i] = clip(x[i] + tmp[i]);
  normalize(normalized, x);
  project(hidden, weights.up, normalized);
  for (auto &v : hidden)
    if (v < 0)
      v = 0;
  project(tmp, weights.down, hidden);
  for (int i = 0; i < 32; ++i)
    x[i] = clip(x[i] + tmp[i]);
  normalize(normalized, x);
  for (int i = 0; i < 64; ++i)
    logits[pos][i] = dot(normalized, weights.embed[i], 32);
}

int main() {
  produced = 0;
  if (!prompt_len || prompt_len >= 32 || !new_tokens || new_tokens > 32 - prompt_len)
    return 1;
  for (unsigned i = 0; i < prompt_len; ++i)
    if (ids[i] >= 64)
      return 1;
  uint32_t start = cycles();
  for (unsigned pos = 0; pos + 1 < prompt_len + new_tokens; ++pos) {
    forward(pos);
    if (pos + 1 < prompt_len)
      continue;
    unsigned best = 0;
    for (unsigned i = 1; i < 64; ++i)
      if (logits[pos][i] > logits[pos][best])
        best = i;
    ids[pos + 1]         = best;
    unsigned step        = pos + 1 - prompt_len;
    elapsed_cycles[step] = cycles() - start;
    produced             = step + 1;
    if (best == 1)
      break;
  }
  return 0;
}
