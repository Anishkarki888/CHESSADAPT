# pipeline/run_pipeline.py
# Single entry point to run the full pairer pipeline end-to-end.
#
# Usage:
#   python -m pipeline.run_pipeline
#   python -m pipeline.run_pipeline --positions data/positions/positions.jsonl
#   python -m pipeline.run_pipeline --tasks-dir data/tasks --sample 3

import argparse
import time

from pipeline.pairer import run as run_pairer
from pipeline.serializer import print_sample

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ChessAdapt pairer — generates T1/T2/T3 task JSONL files."
    )
    parser.add_argument(
        "--positions",
        default="data/positions/positions.jsonl",
        help="Input positions JSONL (default: data/positions/positions.jsonl)",
    )
    parser.add_argument(
        "--tasks-dir",
        default="data/tasks",
        help="Output directory for task JSONL files (default: data/tasks)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="After writing, print N sample items from each file (default: 0)",
    )
    args = parser.parse_args()

    print("\nChessAdapt — Pairer Pipeline")
    print("=" * 50)

    start = time.time()
    run_pairer(positions_path=args.positions, tasks_dir=args.tasks_dir)
    elapsed = time.time() - start

    print(f"\nPairer completed in {elapsed:.1f}s")

    if args.sample > 0:
        import os
        for fname in ("t1_tasks.jsonl", "t2_tasks.jsonl", "t3_tasks.jsonl"):
            path = os.path.join(args.tasks_dir, fname)
            if os.path.exists(path):
                print(f"\n── Sample from {fname} ──────────────────────────")
                print_sample(path, n=args.sample)


if __name__ == "__main__":
    main()
