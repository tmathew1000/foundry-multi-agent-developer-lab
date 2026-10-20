import runpy
import unittest
from dataclasses import replace
from pathlib import Path

from travel_buddy.agents import AgentSpec, coordinator_spec, specialist_specs
from travel_buddy.checkpointing import restore_plan, start_plan
from travel_buddy.tools import convert_currency, estimate_trip_total, search_flights


class AgentSpecificationTests(unittest.TestCase):
    """Static specification contracts, not proof of live model routing."""

    def test_coordinator_requires_tool_backed_currency_delegation(self) -> None:
        self.assert_currency_contracts(coordinator_spec(), specialist_specs()[0])

    def assert_currency_contracts(self, coordinator: AgentSpec, flights: AgentSpec) -> None:
        # Vocabulary checks flag omissions, not instruction meaning or live routing.
        for term in (
            "Flights",
            "convert_currency",
            "standalone",
            "hotel-budget",
            "unsupported_currency",
            "exchange rates",
            "limitation",
        ):
            self.assertIn(term.casefold(), coordinator.instructions.casefold())
        for term in ("currency", "standalone", "hotel-budget", "convert_currency"):
            self.assertIn(term, flights.description.casefold())
        for term in (
            "convert_currency",
            "standalone",
            "hotel-budget",
            "unsupported_currency",
            "unsupported",
            "limitation",
            "estimated rate",
        ):
            self.assertIn(term, flights.instructions.casefold())
        self.assertEqual("Coordinator", coordinator.name)
        self.assertEqual("Flights", flights.name)
        self.assertEqual((search_flights, convert_currency), flights.tools)
        self.assertEqual((estimate_trip_total,), coordinator.tools)

    def test_flights_advertises_and_requires_currency_conversion(self) -> None:
        flights, hotels, activities = specialist_specs()

        self.assertIn("flight options", flights.description)
        self.assertIn("currency conversions", flights.description)
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
                self.assert_currency_contracts(checkpoint_coordinator, checkpoint_flights)
                self.assertIn(
                    "Delegate all requested currency conversions to Flights",
                    checkpoint_coordinator.instructions,
                )
                self.assertIn(
                    "Do not terminate or answer a conversion request before Flights",
                    checkpoint_coordinator.instructions,
                )
                self.assertIn(
                    "Never invent exchange rates or substitute estimates",
                    checkpoint_coordinator.instructions,
                )
                self.assertIn(
                    "Call convert_currency for every currency conversion request",
                    checkpoint_flights.instructions,
                )
                self.assertIn(
                    "even if a currency may be unsupported", checkpoint_flights.instructions
                )
                self.assertIn(
                    "without a numeric conversion or estimated rate",
                    checkpoint_flights.instructions,
                )

    def test_instruction_experiment_need_not_match_checkpoints(self) -> None:
        coordinator = coordinator_spec()
        candidate = replace(
            coordinator,
            description="Coordinates relevant travel specialists.",
            instructions=coordinator.instructions.replace(
                "Coordinate Flights, Hotels, and Activities.",
                "Coordinate relevant Flights, Hotels, and Activities work.",
            )
            + " Avoid unnecessary specialist calls.",
        )
        self.assert_currency_contracts(candidate, specialist_specs()[0])

    def test_currency_contract_detects_missing_tool_and_guidance(self) -> None:
        flights = specialist_specs()[0]
        for candidate in (
            replace(flights, tools=(search_flights,)),
            replace(flights, instructions="Answer currency questions."),
        ):
            with self.subTest(candidate=candidate), self.assertRaises(AssertionError):
                self.assert_currency_contracts(coordinator_spec(), candidate)

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
