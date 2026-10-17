from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .config import ConfigurationError, TravelBuddySettings
from .foundry_iq import FoundryIQGroundingProvider
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
    if settings.grounding.provider == "local":
        return DestinationGroundingProvider(settings.grounding.data_path)
    if settings.grounding.provider == "foundry_iq":
        return FoundryIQGroundingProvider(
            endpoint=settings.grounding.search_endpoint or "",
            knowledge_base=settings.grounding.knowledge_base or "",
            knowledge_source=settings.grounding.knowledge_source or "",
            api_version=settings.grounding.api_version,
        )
    raise ConfigurationError(f"Unsupported grounding provider: {settings.grounding.provider}")
