"""Run the pre-registered Phase 9 debug and primary MaskablePPO experiments."""

from __future__ import annotations

import argparse

from src.training_v3 import PRIMARY_TRAINING_SEEDS
from src.training_v3.training import run_debug, run_primary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--debug-repeat", action="store_true")
    parser.add_argument("--seed", type=int, choices=PRIMARY_TRAINING_SEEDS)
    args = parser.parse_args()
    if args.debug:
        run_debug()
    elif args.debug_repeat:
        run_debug("debug_repeat_seed1101")
    elif args.seed is not None:
        run_primary(args.seed)
    else:
        parser.error("choose --debug, --debug-repeat, or --seed")


if __name__ == "__main__":
    main()
