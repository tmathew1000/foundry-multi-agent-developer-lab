from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigurationError(RuntimeError):
    pass


def resolve_model_deployment(values: Mapping[str, str]) -> str | None:
    explicit_name = values.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    if explicit_name and explicit_name.strip():
        return explicit_name.strip()

    deployments_payload = values.get("AI_PROJECT_DEPLOYMENTS")
    if not deployments_payload or not deployments_payload.strip():
        return None
    try:
        deployments = json.loads(deployments_payload)
    except json.JSONDecodeError as direct_error:
        try:
            unescaped_payload = json.loads(f'"{deployments_payload}"')
            deployments = json.loads(unescaped_payload)
        except (json.JSONDecodeError, TypeError):
            raise ConfigurationError(
                "AI_PROJECT_DEPLOYMENTS must contain valid JSON."
            ) from direct_error
    if not isinstance(deployments, list):
        raise ConfigurationError("AI_PROJECT_DEPLOYMENTS must be a JSON array.")

    names: list[str] = []
    for deployment in deployments:
        if not isinstance(deployment, dict):
            raise ConfigurationError(
                "Each AI_PROJECT_DEPLOYMENTS entry must be a JSON object."
            )
        name = deployment.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError(
                "Each AI_PROJECT_DEPLOYMENTS entry must have a non-empty name."
            )
        names.append(name.strip())

    if len(names) == 1:
        return names[0]
    if len(names) > 1:
        raise ConfigurationError(
            "AZURE_AI_MODEL_DEPLOYMENT_NAME is required when AI_PROJECT_DEPLOYMENTS "
            "contains multiple deployments."
        )
    return None


@dataclass(frozen=True)
class GroundingSettings:
    data_path: str = "data/destinations.json"

    @property
    def enabled(self) -> bool:
        return bool(self.data_path)

    def validate(self) -> None:
        if not self.data_path.strip():
            raise ConfigurationError("TRAVEL_BUDDY_DESTINATIONS_PATH cannot be blank.")


@dataclass(frozen=True)
class TravelBuddySettings:
    project_endpoint: str | None
    model_deployment: str | None
    mcp_url: str | None = None
    app_insights_connection_string: str | None = None
    grounding: GroundingSettings = GroundingSettings()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> TravelBuddySettings:
        values = os.environ if env is None else env
        settings = cls(
            project_endpoint=values.get("FOUNDRY_PROJECT_ENDPOINT"),
            model_deployment=resolve_model_deployment(values),
            mcp_url=values.get("TRAVEL_BUDDY_MCP_URL"),
            app_insights_connection_string=values.get("APPLICATIONINSIGHTS_CONNECTION_STRING"),
            grounding=GroundingSettings(
                data_path=values.get("TRAVEL_BUDDY_DESTINATIONS_PATH", "data/destinations.json"),
            ),
        )
        settings.grounding.validate()
        return settings

    def require_cloud(self) -> None:
        missing = []
        if not self.project_endpoint:
            missing.append("FOUNDRY_PROJECT_ENDPOINT")
        if not self.model_deployment:
            missing.append("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        if missing:
            raise ConfigurationError(
                "Missing required hosted-agent configuration: " + ", ".join(missing)
            )
