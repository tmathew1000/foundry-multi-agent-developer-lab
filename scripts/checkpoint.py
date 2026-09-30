from __future__ import annotations

import argparse
import filecmp
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", choices=["01-tools", "02-orchestration"])
    args = parser.parse_args()
    root = Path(__file__).parents[1] / "checkpoints" / args.checkpoint
    starter = root / "starter"
    solution = root / "solution"
    if not starter.is_dir() or not solution.is_dir():
        raise RuntimeError(f"Checkpoint {args.checkpoint} is incomplete")
    comparison = filecmp.dircmp(starter, solution)
    changed = sorted(comparison.diff_files + comparison.left_only + comparison.right_only)
    print(f"{args.checkpoint}: {len(changed)} learner change(s)")
    for path in changed:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
