from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from travel_buddy.cloud_evaluation import compare_metrics, load_result, validate_comparison


def _display_score(value: float | str | None, *, signed: bool = False) -> str:
    if value is None:
        return "unverified"
    return format(float(value), "+.3f" if signed else ".3f")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--output", type=Path)
    root = Path(__file__).parents[1]
    parser.add_argument("--results-dir", type=Path, default=root / ".foundry" / "results")
    parser.add_argument("--fallback", action="store_true")
    args = parser.parse_args()
    results_dir = root / "artifacts" / "evaluations" if args.fallback else args.results_dir
    try:
        baseline = load_result(results_dir / f"{args.baseline}.json")
        candidate = load_result(results_dir / f"{args.candidate}.json")
        notice = validate_comparison(baseline, candidate)
        rows = compare_metrics(baseline, candidate)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(notice)
    print("Missing scores are unverified, not zero. Verify tool evidence in the actual traces.")
    print(f"{'Metric':24} {'Baseline':>10} {'Candidate':>10} {'Change':>10}")
    for row in rows:
        print(
            f"{row['metric'][:24]:24} "
            f"{_display_score(row['baseline']):>10} "
            f"{_display_score(row['candidate']):>10} "
            f"{_display_score(row['change'], signed=True):>10}"
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
