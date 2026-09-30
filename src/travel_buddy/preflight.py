from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class AzureAccount:
    subscription_id: str
    subscription_name: str
    state: str
    tenant_id: str


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    level: str
    detail: str

    @property
    def blocking(self) -> bool:
        return self.level == "BLOCKER"


def parse_azure_account(payload: str) -> AzureAccount:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Azure CLI returned invalid account JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Azure CLI account response must be a JSON object")

    required = {
        "id": "subscription ID",
        "name": "subscription name",
        "state": "subscription state",
        "tenantId": "tenant ID",
    }
    parsed: dict[str, str] = {}
    for key, description in required.items():
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Azure CLI account response is missing {description}")
        parsed[key] = item.strip()
    return AzureAccount(
        subscription_id=parsed["id"],
        subscription_name=parsed["name"],
        state=parsed["state"],
        tenant_id=parsed["tenantId"],
    )


def parse_azd_env_values(payload: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, line in enumerate(payload.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, raw_value = stripped.partition("=")
        if not separator or not _ENV_NAME.fullmatch(name):
            raise ValueError(f"Invalid azd environment value on line {line_number}")
        values[name] = _decode_env_value(raw_value, line_number)
    return values


def merge_environment_values(
    process_environment: Mapping[str, str],
    azd_environment: Mapping[str, str],
) -> dict[str, str]:
    merged = dict(azd_environment)
    merged.update(
        {
            key: value
            for key, value in process_environment.items()
            if isinstance(value, str) and value.strip()
        }
    )
    return merged


def post_provision_checks(values: Mapping[str, str]) -> list[PreflightCheck]:
    endpoint = _first_value(
        values,
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_AI_PROJECT_ENDPOINT",
        "AZURE_AIPROJECT_ENDPOINT",
    )
    model = _first_value(values, "AZURE_AI_MODEL_DEPLOYMENT_NAME")
    mcp_url = _first_value(values, "TRAVEL_BUDDY_MCP_URL")
    return [
        _url_check(
            "foundry-project-endpoint",
            endpoint,
            "FOUNDRY_PROJECT_ENDPOINT or AZURE_AI_PROJECT_ENDPOINT",
            require_remote=False,
        ),
        _required_value_check(
            "model-deployment",
            model,
            "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        ),
        _url_check(
            "remote-mcp-url",
            mcp_url,
            "TRAVEL_BUDDY_MCP_URL",
            require_remote=True,
        ),
    ]


def caveat_checks() -> list[PreflightCheck]:
    return [
        PreflightCheck(
            "role-assignments",
            "CAVEAT",
            (
                "Login does not prove deployment authorization. Provisioning can require "
                "resource creation and role-assignment permissions at the target scope."
            ),
        ),
        PreflightCheck(
            "regional-quota",
            "CAVEAT",
            (
                "Model and Container Apps quota is subscription- and region-specific; "
                "azd provisioning remains the authoritative capacity check."
            ),
        ),
        PreflightCheck(
            "azure-policy",
            "CAVEAT",
            (
                "Azure Policy can deny resource types, SKUs, regions, public access, "
                "or role assignments even when login and subscription checks pass."
            ),
        ),
    ]


def _decode_env_value(raw_value: str, line_number: int) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid quoted azd environment value on line {line_number}") from exc
        if not isinstance(decoded, str):
            raise ValueError(f"Quoted azd environment value on line {line_number} must be a string")
        return decoded
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1]
    return value


def _first_value(values: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = values.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _required_value_check(name: str, value: str | None, environment_name: str) -> PreflightCheck:
    if value:
        return PreflightCheck(name, "OK", value)
    return PreflightCheck(
        name,
        "BLOCKER",
        f"Missing {environment_name}; run azd provision/deploy and load azd environment values.",
    )


def _url_check(
    name: str,
    value: str | None,
    environment_name: str,
    *,
    require_remote: bool,
) -> PreflightCheck:
    if not value:
        return PreflightCheck(
            name,
            "BLOCKER",
            f"Missing {environment_name}; run azd provision/deploy and load "
            "azd environment values.",
        )
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return PreflightCheck(
            name,
            "BLOCKER",
            f"{environment_name} must be an absolute HTTP(S) URL.",
        )
    if require_remote and parsed.hostname.casefold() in {"localhost", "127.0.0.1", "::1"}:
        return PreflightCheck(
            name,
            "BLOCKER",
            f"{environment_name} must reference the deployed remote MCP service.",
        )
    return PreflightCheck(name, "OK", value)
