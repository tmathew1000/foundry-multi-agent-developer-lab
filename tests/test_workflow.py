import unittest

from travel_buddy.config import TravelBuddySettings
from travel_buddy.grounding import DestinationGroundingProvider
from travel_buddy.workflow import build_travel_buddy


class FakeAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.name = kwargs["name"]


class FakeWorkflow:
    def __init__(self, builder):
        self.builder = builder
        self.as_agent_name = None

    def as_agent(self, name):
        self.as_agent_name = name
        return {"name": name}


class FakeGroupChatBuilder:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def build(self):
        return FakeWorkflow(self)


class WorkflowTests(unittest.TestCase):
    def test_builds_four_logical_agents_and_wraps_workflow_as_agent(self) -> None:
        settings = TravelBuddySettings(None, None)
        built = build_travel_buddy(
            settings,
            agent_factory=FakeAgent,
            client_factory=lambda role: f"client:{role}",
            group_chat_factory=FakeGroupChatBuilder,
            mcp_tool_factory=lambda _: "mcp",
        )

        self.assertEqual("Coordinator", built.coordinator.name)
        self.assertEqual(
            ["Flights", "Hotels", "Activities"],
            [agent.name for agent in built.specialists],
        )
        self.assertEqual("TravelBuddy", built.workflow.as_agent_name)
        self.assertEqual({"name": "TravelBuddy"}, built.agent)
        flight_tools = built.specialists[0].kwargs["tools"]
        self.assertEqual(
            ["search_flights", "convert_currency"],
            [tool.__name__ for tool in flight_tools],
        )
        activity_tools = built.specialists[2].kwargs["tools"]
        self.assertEqual(["mcp"], activity_tools)
        hotel_providers = built.specialists[1].kwargs["context_providers"]
        activity_providers = built.specialists[2].kwargs["context_providers"]
        self.assertEqual(1, len(hotel_providers))
        self.assertIs(hotel_providers[0], activity_providers[0])
        self.assertIsInstance(hotel_providers[0], DestinationGroundingProvider)

    def test_partial_factory_injection_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be supplied together"):
            build_travel_buddy(
                TravelBuddySettings(None, None),
                agent_factory=FakeAgent,
            )


if __name__ == "__main__":
    unittest.main()
