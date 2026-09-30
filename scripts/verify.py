from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from travel_buddy.evaluation import load_cases


def run_all(root: Path) -> int:
    root = Path(__file__).parents[1]
    with (root / ".devcontainer" / "devcontainer.json").open(encoding="utf-8") as stream:
        json.load(stream)
    cases = load_cases(root / "evaluations" / "travel_buddy_cases.jsonl")
    if not 6 <= len(cases) <= 10:
        raise RuntimeError("Evaluation dataset must contain between 6 and 10 cases")
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main() -> int:
    root = Path(__file__).parents[1]
    if len(sys.argv) == 1:
        return run_all(root)
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify.py [0|1|2|3|4|5|all]")
    command = [sys.executable, str(root / "scripts" / "verify_module.py"), sys.argv[1]]
    completed = subprocess.run(command, cwd=root, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
