from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigurationError(RuntimeError):
    pass


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
            model_deployment=values.get("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
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
