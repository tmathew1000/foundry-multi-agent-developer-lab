from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from travel_buddy.cloud_evaluation import evaluation_rows


def run_all(root: Path) -> int:
    root = Path(__file__).parents[1]
    with (root / ".devcontainer" / "devcontainer.json").open(encoding="utf-8") as stream:
        json.load(stream)
    evaluation_rows(root / "evaluations" / "travel_buddy_cases.jsonl")
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def main() -> int:
    root = Path(__file__).parents[1]
    if len(sys.argv) == 1:
        return run_all(root)
    command = [sys.executable, str(root / "scripts" / "verify_module.py"), *sys.argv[1:]]
    completed = subprocess.run(command, cwd=root, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
