from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from travel_buddy.preflight import parse_azd_env_values, post_provision_checks
from travel_buddy.verification import module_checks, normalize_module_identifier


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("module")
    evidence = parser.add_mutually_exclusive_group()
    evidence.add_argument("--results-dir", type=Path)
    evidence.add_argument("--fallback", action="store_true")
    args = parser.parse_args()
    print("Configuration/static checks only; no live agent or tool calls are made.")
    root = Path(__file__).parents[1]
    try:
        modules = normalize_module_identifier(args.module)
    except ValueError as exc:
        parser.error(str(exc))

    failed = False
    for module in modules:
        checks = module_checks(root, module, results_dir=args.results_dir, fallback=args.fallback)
        if module == "0":
            checks.append(
                (
                    "deployed Foundry, model, MCP, and Foundry IQ environment values",
                    lambda: _post_provision_environment_is_ready(root),
                )
            )
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
                "0": "Foundry, model, MCP, and Foundry IQ configuration is present",
                "1": "hosted-agent baseline is valid",
                "2": "function, MCP, local grounding, and Foundry IQ contracts are valid",
                "4": "tracing configuration is present",
                "5": "baseline and candidate results are comparable",
            }
            print(f"PASS Module {module}: {descriptions[module]}")
    return 1 if failed else 0


def _post_provision_environment_is_ready(root: Path) -> bool:
    try:
        completed = subprocess.run(
            ["azd", "env", "get-values"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"BLOCKER azd environment: {exc}", file=sys.stderr)
        return False
    if completed.returncode != 0:
        print(
            f"BLOCKER azd environment: {completed.stderr.strip() or 'Select an azd environment.'}",
            file=sys.stderr,
        )
        return False
    try:
        values = parse_azd_env_values(completed.stdout)
    except ValueError as exc:
        print(f"BLOCKER azd environment: {exc}", file=sys.stderr)
        return False
    blockers = [check for check in post_provision_checks(values) if check.blocking]
    for check in blockers:
        print(f"BLOCKER {check.name}: {check.detail}", file=sys.stderr)
    return not blockers


if __name__ == "__main__":
    raise SystemExit(main())
