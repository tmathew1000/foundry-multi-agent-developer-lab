from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from travel_buddy.cloud_evaluation import compare_metrics, load_result


def _result_path(root: Path, label: str) -> Path:
    generated = root / ".foundry" / "results" / f"{label}.json"
    if generated.is_file():
        return generated
    return root / "artifacts" / "evaluations" / f"{label}.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).parents[1]
    try:
        baseline = load_result(_result_path(root, args.baseline))
        candidate = load_result(_result_path(root, args.candidate))
        rows = compare_metrics(baseline, candidate)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"{'Metric':24} {'Baseline':>10} {'Candidate':>10} {'Change':>10}")
    for row in rows:
        print(
            f"{row['metric'][:24]:24} "
            f"{row['baseline']:10.3f} "
            f"{row['candidate']:10.3f} "
            f"{row['change']:+10.3f}"
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
