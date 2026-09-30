import unittest

from travel_buddy.agents import specialist_specs


class AgentSpecificationTests(unittest.TestCase):
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
