from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from travel_buddy.preflight import (
    PreflightCheck,
    caveat_checks,
    merge_environment_values,
    parse_azd_env_values,
    parse_azure_account,
    post_provision_checks,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--post-provision",
        action="store_true",
        help="Require deployed Foundry, model, and remote MCP environment values.",
    )
    args = parser.parse_args(argv)

    checks = [
        PreflightCheck(
            "python>=3.11",
            "OK" if sys.version_info >= (3, 11) else "BLOCKER",
            f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    ]
    az_path = shutil.which("az")
    azd_path = shutil.which("azd")
    checks.extend(
        [
            PreflightCheck(
                "azure-cli",
                "OK" if az_path else "BLOCKER",
                az_path or "Azure CLI (az) was not found on PATH.",
            ),
            PreflightCheck(
                "azd",
                "OK" if azd_path else "BLOCKER",
                azd_path or "Azure Developer CLI (azd) was not found on PATH.",
            ),
        ]
    )
    if az_path:
        checks.extend(_azure_account_checks(az_path))

    if args.post_provision:
        azd_values: dict[str, str] = {}
        if azd_path:
            azd_values, azd_check = _load_azd_values(azd_path)
            checks.append(azd_check)
        values = merge_environment_values(os.environ, azd_values)
        checks.extend(post_provision_checks(values))

    checks.extend(caveat_checks())
    for check in checks:
        print(f"[{check.level}] {check.name}: {check.detail}")
    return 1 if any(check.blocking for check in checks) else 0


def _azure_account_checks(az_executable: str) -> list[PreflightCheck]:
    completed = _run([az_executable, "account", "show", "--output", "json"])
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "Run 'az login' and select a subscription."
        return [PreflightCheck("azure-login", "BLOCKER", detail)]
    try:
        account = parse_azure_account(completed.stdout)
    except ValueError as exc:
        return [PreflightCheck("azure-login", "BLOCKER", str(exc))]
    login = PreflightCheck(
        "azure-login",
        "OK",
        f"Signed in to tenant {account.tenant_id}.",
    )
    if account.state.casefold() != "enabled":
        subscription = PreflightCheck(
            "enabled-subscription",
            "BLOCKER",
            (
                f"Subscription {account.subscription_name} ({account.subscription_id}) "
                f"is {account.state}, not Enabled."
            ),
        )
    else:
        subscription = PreflightCheck(
            "enabled-subscription",
            "OK",
            f"{account.subscription_name} ({account.subscription_id})",
        )
    return [login, subscription]


def _load_azd_values(azd_executable: str) -> tuple[dict[str, str], PreflightCheck]:
    completed = _run([azd_executable, "env", "get-values"])
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "No azd environment is selected."
        return {}, PreflightCheck("azd-environment", "BLOCKER", detail)
    try:
        values = parse_azd_env_values(completed.stdout)
    except ValueError as exc:
        return {}, PreflightCheck("azd-environment", "BLOCKER", str(exc))
    return values, PreflightCheck(
        "azd-environment",
        "OK",
        f"Loaded {len(values)} value(s) from the selected azd environment.",
    )


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(command, 1, "", str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
