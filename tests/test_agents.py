import runpy
import unittest
from pathlib import Path

from travel_buddy.agents import coordinator_spec, specialist_specs
from travel_buddy.checkpointing import restore_plan, start_plan
from travel_buddy.tools import convert_currency, search_flights


class AgentSpecificationTests(unittest.TestCase):
    """Static specification contracts, not proof of live model routing."""

    def test_coordinator_requires_tool_backed_currency_delegation(self) -> None:
        instructions = coordinator_spec().instructions

        self.assertIn("Delegate all requested currency conversions to Flights", instructions)
        self.assertIn("standalone conversions and hotel-budget conversions", instructions)
        self.assertIn(
            "Do not terminate or answer a conversion request before Flights", instructions
        )
        self.assertIn("Never invent exchange rates or substitute estimates", instructions)
        self.assertIn("unsupported_currency", instructions)
        self.assertIn("without a numeric conversion", instructions)

    def test_flights_advertises_and_requires_currency_conversion(self) -> None:
        flights, hotels, activities = specialist_specs()

        self.assertIn("flight options", flights.description)
        self.assertIn("currency conversions", flights.description)
        self.assertIn("standalone and hotel-budget", flights.description)
        self.assertIn(
            "Call convert_currency for every currency conversion request", flights.instructions
        )
        self.assertIn("even if a currency may be unsupported", flights.instructions)
        self.assertIn("unsupported_currency", flights.instructions)
        self.assertIn("without a numeric conversion or estimated rate", flights.instructions)
        self.assertEqual((search_flights, convert_currency), flights.tools)
        self.assertNotIn(convert_currency, coordinator_spec().tools)
        self.assertNotIn(convert_currency, hotels.tools)
        self.assertNotIn(convert_currency, activities.tools)

    def test_module_three_checkpoints_preserve_currency_routing_specs(self) -> None:
        root = Path(__file__).parents[1]
        for plan in (start_plan, restore_plan):
            operation = next(
                item for item in plan(root, "3") if item.destination.name == "agents.py"
            )
            with self.subTest(checkpoint=operation.source):
                namespace = runpy.run_path(
                    str(operation.source),
                    run_name="travel_buddy._checkpoint_agents",
                )
                checkpoint_coordinator = namespace["coordinator_spec"]()
                checkpoint_flights = namespace["specialist_specs"]()[0]
                for expected, actual in (
                    (coordinator_spec(), checkpoint_coordinator),
                    (specialist_specs()[0], checkpoint_flights),
                ):
                    self.assertEqual(expected.name, actual.name)
                    self.assertEqual(expected.description, actual.description)
                    self.assertEqual(expected.instructions, actual.instructions)
                    self.assertEqual(expected.tools, actual.tools)

    def test_mcp_is_scoped_to_hotels_and_activities(self) -> None:
        grounding = object()
        flights, hotels, activities = specialist_specs(
            mcp_tool="remote-mcp",
            grounding_provider=grounding,
        )

        self.assertNotIn("remote-mcp", flights.tools)
        self.assertIn("remote-mcp", hotels.tools)
        self.assertIn("remote-mcp", activities.tools)
        self.assertEqual((grounding,), hotels.context_providers)
        self.assertEqual((grounding,), activities.context_providers)


if __name__ == "__main__":
    unittest.main()
