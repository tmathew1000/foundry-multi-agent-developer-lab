from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .config import ConfigurationError, TravelBuddySettings
from .grounding import DestinationGroundingProvider

ToolFactory = Callable[[TravelBuddySettings], Any]
ProviderFactory = Callable[[TravelBuddySettings], Any]


def build_mcp_tool(settings: TravelBuddySettings) -> Any | None:
    if not settings.mcp_url:
        return None
    try:
        from agent_framework import MCPStreamableHTTPTool
    except ImportError as exc:
        raise RuntimeError(
            "Install the Agent Framework dependencies before enabling MCP integration."
        ) from exc
    return MCPStreamableHTTPTool(
        name="travel_buddy_remote_tools",
        description="Destination activity and advisory tools exposed by TravelBuddy MCP.",
        url=settings.mcp_url,
    )


def build_grounding_provider(
    settings: TravelBuddySettings,
    *,
    factory: ProviderFactory | None,
) -> Any:
    settings.grounding.validate()
    if not settings.grounding.enabled:
        raise ConfigurationError("Destination grounding must be enabled.")
    if factory is not None:
        return factory(settings)
    return DestinationGroundingProvider(settings.grounding.data_path)
