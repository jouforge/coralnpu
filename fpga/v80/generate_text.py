import argparse
import asyncio
from pathlib import Path
import time

from lm.inference import generate, load
from lm.model import Reference, decode
from run_board import open_board


async def run(args):
    weights = args.weights.read_bytes()
    reference = Reference(weights) if args.verify else None
    with open_board(args.device, args.timeout) as board:
        start = time.perf_counter()
        await load(board, args.elf, weights)
        print(
            f"ELF and weights load: {(time.perf_counter()-start)*1000:.2f} ms"
        )
        for prompt in args.prompt:
            tokens, ticks, seconds = await generate(
                board, prompt, args.new_tokens, reference
            )
            print(f"{prompt}{decode(tokens)}")
            print(
                f"tokens={tokens} core_first_token_ms={ticks[0]/25000:.3f} "
                f"core_decode_cycles={list(map(int, ticks[1:]-ticks[:-1]))} "
                f"end_to_end_tokens_per_s={len(tokens)/seconds:.2f}"
            )
            if args.verify:
                print(
                    "PASS: all logits and token IDs match the integer reference"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path(__file__).parent / "lm" / "stories.bin"
    )
    parser.add_argument("--prompt", action="append", required=True)
    parser.add_argument("--new-tokens", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument("--verify", action="store_true")
    asyncio.run(run(parser.parse_args()))
