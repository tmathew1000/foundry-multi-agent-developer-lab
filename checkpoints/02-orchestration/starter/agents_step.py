from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .tools import convert_currency, estimate_trip_total, search_flights, search_hotels

Tool = Callable[..., Any] | Any


@dataclass(frozen=True)
class AgentSpec:
    name: str
    description: str
    instructions: str
    tools: tuple[Tool, ...] = ()
    context_providers: tuple[Any, ...] = ()


def coordinator_spec() -> AgentSpec:
    return AgentSpec(
        name="Coordinator",
        description="Coordinates specialists and produces the final travel plan.",
        instructions=(
            "Coordinate Flights, Hotels, and Activities. Ask for missing trip constraints, "
            "delegate only relevant work, reconcile prices, and produce a concise itinerary "
            "with assumptions and a USD total. Never claim a booking was completed."
        ),
        tools=(estimate_trip_total,),
    )


def specialist_specs(
    *,
    mcp_tool: Tool | None = None,
    grounding_provider: Any | None = None,
) -> tuple[AgentSpec, AgentSpec, AgentSpec]:
    hotel_tools = tuple(tool for tool in (search_hotels, mcp_tool) if tool is not None)
    grounding_providers = (grounding_provider,) if grounding_provider is not None else ()
    return (
        AgentSpec(
            name="Flights",
            description="Finds and compares flight options.",
            instructions=(
                "Use the flight search function for flight requests and the currency function "
                "for price conversions. Return at most three flight options, state route, date, "
                "stops, price, and tradeoffs. Report unsupported currencies exactly as returned "
                "by the tool. Do not invent availability or exchange rates."
            ),
            tools=(search_flights, convert_currency),
        ),
        AgentSpec(
            name="Hotels",
            description="Finds lodging that matches dates and budget.",
            instructions=(
                "Use the hotel search function. Compare total stay prices and call out the "
                "number of nights. Use destination grounding for area guidance and cite its "
                "source IDs. Do not claim a reservation was made."
            ),
            tools=hotel_tools,
            context_providers=grounding_providers,
        ),
        # TODO: Replace this placeholder with an Activities AgentSpec that owns
        # the remote MCP tool and destination grounding provider.
        AgentSpec(
            name="Activities",
            description="TODO: define the Activities specialist.",
            instructions="TODO: define activity and itinerary behavior.",
        ),
    )
