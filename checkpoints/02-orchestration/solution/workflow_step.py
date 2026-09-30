from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .agents import AgentSpec, coordinator_spec, specialist_specs
from .config import TravelBuddySettings
from .executors import ContextPreservingAgentExecutor
from .integrations import (
    ProviderFactory,
    ToolFactory,
    build_grounding_provider,
    build_mcp_tool,
)

AgentFactory = Callable[..., Any]
ClientFactory = Callable[[str], Any]
GroupChatFactory = Callable[..., Any]
ExecutorFactory = Callable[[Any], Any]


@dataclass(frozen=True)
class BuiltTravelBuddy:
    agent: Any
    workflow: Any
    coordinator: Any
    specialists: tuple[Any, Any, Any]


def _default_factories(
    settings: TravelBuddySettings,
) -> tuple[AgentFactory, ClientFactory, GroupChatFactory]:
    settings.require_cloud()
    try:
        from agent_framework import Agent
        from agent_framework.foundry import FoundryChatClient
        from agent_framework.orchestrations import GroupChatBuilder
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError(
            "Install the project dependencies before building the hosted workflow."
        ) from exc
    credential = DefaultAzureCredential()

    def client_factory(_: str) -> Any:
        return FoundryChatClient(
            project_endpoint=settings.project_endpoint,
            model=settings.model_deployment,
            credential=credential,
        )

    return Agent, client_factory, GroupChatBuilder


def _create_agent(
    spec: AgentSpec,
    *,
    agent_factory: AgentFactory,
    client_factory: ClientFactory,
) -> Any:
    return agent_factory(
        name=spec.name,
        description=spec.description,
        instructions=spec.instructions,
        client=client_factory(spec.name),
        tools=list(spec.tools),
        context_providers=list(spec.context_providers),
    )


def build_travel_buddy(
    settings: TravelBuddySettings,
    *,
    agent_factory: AgentFactory | None = None,
    client_factory: ClientFactory | None = None,
    group_chat_factory: GroupChatFactory | None = None,
    executor_factory: ExecutorFactory = ContextPreservingAgentExecutor,
    mcp_tool_factory: ToolFactory = build_mcp_tool,
    grounding_provider_factory: ProviderFactory | None = None,
) -> BuiltTravelBuddy:
    supplied = (agent_factory, client_factory, group_chat_factory)
    if any(item is None for item in supplied):
        if any(item is not None for item in supplied):
            raise ValueError(
                "agent_factory, client_factory, and group_chat_factory must be supplied together."
            )
        agent_factory, client_factory, group_chat_factory = _default_factories(settings)

    assert agent_factory is not None
    assert client_factory is not None
    assert group_chat_factory is not None
    mcp_tool = mcp_tool_factory(settings)
    grounding_provider = build_grounding_provider(settings, factory=grounding_provider_factory)
    coordinator = _create_agent(
        coordinator_spec(),
        agent_factory=agent_factory,
        client_factory=client_factory,
    )
    specialists = tuple(
        _create_agent(
            spec,
            agent_factory=agent_factory,
            client_factory=client_factory,
        )
        for spec in specialist_specs(mcp_tool=mcp_tool, grounding_provider=grounding_provider)
    )
    specialist_executors = [executor_factory(agent) for agent in specialists]
    workflow = group_chat_factory(
        participants=specialist_executors,
        intermediate_output_from=specialist_executors,
        orchestrator_agent=coordinator,
        max_rounds=8,
    ).build()
    hosted_agent = workflow.as_agent(name="TravelBuddy")
    return BuiltTravelBuddy(
        agent=hosted_agent,
        workflow=workflow,
        coordinator=coordinator,
        specialists=specialists,
    )
