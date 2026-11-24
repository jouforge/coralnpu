import math
import string

import numpy as np

BOS, EOS, UNKNOWN = 0, 1, 2
CHARS = string.ascii_letters + " \n.,!?'\"-"
assert len(CHARS) + 3 == 64
IDS = {c: i + 3 for i, c in enumerate(CHARS)}
SHAPES = ((64, 32), (32, 32), (96, 32), (32, 32), (64, 32), (32, 64))
MODEL_BYTES = sum(math.prod(s) for s in SHAPES) + 512


def encode(text):
    return [BOS] + [IDS.get(c, UNKNOWN) for c in text]


def decode(tokens):
    return "".join(CHARS[t - 3] if t >= 3 else "�" for t in tokens if t != EOS)


def norm(x):
    divisor = math.isqrt(int(x @ x) // 32 + 1)
    return np.trunc(x * 32 / divisor).astype(np.int32).clip(-128, 127)


class Reference:

    def __init__(self, blob):
        if len(blob) != MODEL_BYTES:
            raise ValueError("Invalid model size")
        offset = 0
        self.weights = []
        for shape in SHAPES:
            size = math.prod(shape)
            self.weights.append(
                np.frombuffer(blob, np.int8, size,
                              offset).reshape(shape).astype(np.int32)
            )
            offset += size
        self.exp = np.frombuffer(blob, "<u2", 256, offset).astype(np.int32)

    def steps(self, tokens):
        embed, pos, qkv, out, up, down = self.weights
        keys, values = [], []
        for i, token in enumerate(tokens):
            x = (embed[token] + pos[i]).clip(-128, 127)

            def project(w, v):
                return ((w @ v + 64) >> 7).clip(-128, 127)

            q, k, v = np.split(project(qkv, norm(x)), 3)
            keys.append(k)
            values.append(v)
            scores = np.trunc((np.asarray(keys) @ q) / 362).astype(np.int32)
            p = self.exp[(scores.max() - scores).clip(0, 255)]
            context = np.trunc((p @ np.asarray(values)) / p.sum()
                               ).astype(np.int32)
            x = (x + project(out, context)).clip(-128, 127)
            x = (x + project(down,
                             project(up, norm(x)).clip(0))).clip(-128, 127)
            yield embed @ norm(x)

    def generate(self, prompt, count):
        tokens = list(prompt)
        outputs = []
        for logits in self.steps(tokens):
            outputs.append(logits)
            if len(outputs) >= len(prompt):
                token = int(logits.argmax())
                tokens.append(token)
                if token == EOS or len(tokens) == len(prompt) + count:
                    break
        return tokens[len(prompt):], np.array(outputs)
