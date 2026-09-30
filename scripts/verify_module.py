from __future__ import annotations

import argparse
import sys
from pathlib import Path

from travel_buddy.verification import module_checks, normalize_module_identifier


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    args = parser.parse_args()
    root = Path(__file__).parents[1]
    try:
        modules = normalize_module_identifier(args.module)
    except ValueError as exc:
        parser.error(str(exc))

    failed = False
    for module in modules:
        checks = module_checks(root, module)
        module_failed = False
        for description, check in checks:
            if not check():
                failed = True
                module_failed = True
                print(f"FAIL Module {module}: {description}", file=sys.stderr)
            elif module == "3":
                print(f"PASS {description}")
        if not module_failed and module != "3":
            descriptions = {
                "0": "local tools and Azure context are ready",
                "1": "hosted-agent baseline is valid",
                "2": "function, MCP, and grounding contracts are valid",
                "4": "tracing configuration is present",
                "5": "baseline and candidate results are comparable",
            }
            print(f"PASS Module {module}: {descriptions[module]}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
