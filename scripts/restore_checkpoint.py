from __future__ import annotations

import argparse
import sys
from pathlib import Path

from travel_buddy.checkpointing import apply_restore, restore_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).parents[1]
    try:
        operations = restore_plan(root, args.module)
        destinations = apply_restore(operations, dry_run=args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    action = "WOULD REPLACE" if args.dry_run else "REPLACED"
    for destination in destinations:
        print(f"{action} {destination.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
