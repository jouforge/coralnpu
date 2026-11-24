import argparse
import hashlib
from pathlib import Path
import urllib.request

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from model import EOS, Reference, decode, encode

REV = "f54c09fd23315a6f9c86f9dc80f725de7d8f9c64"
HASHES = {
    "train":
    "5352b299dcb1a32898b2d779b145b5a05f3e1265953fd21c264c9f9f9c9ae33d",
    "valid":
    "734193bdb018bb706a5af89c8b423d5ebcbc170c0a6601239baedd4b62450cb7",
}


def corpus(cache, split):
    path = cache / (split + ".txt")
    if not path.exists():
        url = f"https://huggingface.co/datasets/roneneldan/TinyStories/resolve/{REV}/TinyStories-{split}.txt"
        request = urllib.request.Request(
            url, headers={"Range": "bytes=0-2097151"}
        )
        with urllib.request.urlopen(request) as response:
            path.write_bytes(response.read(2097152))
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != HASHES[split]:
        raise ValueError(f"Unexpected corpus hash for {path}")
    tokens = []
    for story in raw.decode("utf8",
                            errors="ignore").split("<|endoftext|>")[:-1]:
        tokens.extend(encode(story.strip()) + [EOS])
    return torch.tensor(tokens)


class Transformer(nn.Module):

    def __init__(self):
        super().__init__()
        self.embed = nn.Embedding(64, 32)
        self.pos = nn.Embedding(32, 32)
        nn.init.normal_(self.embed.weight, std=0.08)
        nn.init.normal_(self.pos.weight, std=0.025)
        self.qkv = nn.Linear(32, 96, bias=False)
        self.out = nn.Linear(32, 32, bias=False)
        self.up = nn.Linear(32, 64, bias=False)
        self.down = nn.Linear(64, 32, bias=False)

    def forward(self, ids):

        def norm(x):
            return F.rms_norm(x, (32, ), eps=1 / 1024).clamp(-4, 3.96875)

        x = (4 * (self.embed(ids) + self.pos(torch.arange(ids.size(1))))
             ).clamp(-4, 3.96875)
        q, k, v = self.qkv(norm(x)).clamp(-4, 3.96875).chunk(3, -1)
        a = F.scaled_dot_product_attention(
            q[:, None], k[:, None], v[:, None], is_causal=True
        )
        x = (x + self.out(a[:, 0]).clamp(-4, 3.96875)).clamp(-4, 3.96875)
        x = (
            x +
            self.down(self.up(norm(x)).clamp(0, 3.96875)).clamp(-4, 3.96875)
        ).clamp(-4, 3.96875)
        return F.linear(norm(x), self.embed.weight) * 3

    def export(self):
        layers = (self.embed, self.pos, self.qkv, self.out, self.up, self.down)
        weights = b"".join(
            (layer.weight.detach() *
             128).round().clamp(-128, 127).to(torch.int8).numpy().tobytes()
            for layer in layers
        )
        table = np.rint(np.exp(-np.arange(256) / 16) * 4096).astype("<u2")
        return weights + table.tobytes()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(2718)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    train, valid = [corpus(args.cache, split) for split in HASHES]
    model = Transformer()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002)

    def batch(data, size):
        starts = torch.randint(len(data) - 32, (size, 1))
        seq = data[starts + torch.arange(33)]
        return seq[:, :-1], seq[:, 1:]

    for _ in range(3000):
        x, y = batch(train, 64)
        loss = F.cross_entropy(model(x).flatten(0, 1), y.flatten())
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    blob = model.export()
    x, y = batch(valid, 128)
    with torch.no_grad():
        fp = F.cross_entropy(model(x).flatten(0, 1), y.flatten()).item()
    ref = Reference(blob)
    scores = np.array([list(ref.steps(row.numpy())) for row in x])
    quant = F.cross_entropy(
        torch.from_numpy(scores * (3 / 4096)).flatten(0, 1), y.flatten()
    ).item()
    freq = (train.bincount(minlength=64) + 1).double()
    baseline = -(freq / freq.sum()).log()[y].mean().item()
    print(
        f"validation nats/token: unigram={baseline:.5f} float={fp:.5f} integer={quant:.5f}"
    )
    print("weights sha256", hashlib.sha256(blob).hexdigest())
    if max(fp, quant) >= baseline:
        raise RuntimeError("Validation loss did not beat the unigram baseline")

    args.output.write_bytes(blob)
    prompt = "Once upon a"
    initial = encode(prompt)
    ids = initial.copy()
    with torch.no_grad():
        for _ in range(12):
            token = model(torch.tensor([ids]))[0, -1].argmax().item()
            ids.append(token)
            if token == EOS:
                break
    quantized, _ = ref.generate(initial, 12)
    print("float:", prompt + decode(ids[len(initial):]))
    print("integer:", prompt + decode(quantized))


if __name__ == "__main__":
    main()
