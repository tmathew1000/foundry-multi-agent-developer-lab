import unittest

from mcp_server.catalog import search_activities, search_lodging


class McpCatalogTests(unittest.TestCase):
    def test_activity_search_filters_interest_and_budget(self) -> None:
        results = search_activities("Tokyo", ["food"], 60)

        self.assertEqual(["Local food market tour"], [item["name"] for item in results])

    def test_lodging_search_filters_budget_and_amenities(self) -> None:
        results = search_lodging("Tokyo", 180, ["wifi", "breakfast"])

        self.assertEqual(["Northwind Central"], [item["name"] for item in results])
        self.assertEqual("Workshop inventory", results[0]["notice"])

    def test_lodging_search_rejects_negative_budget(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            search_lodging("Tokyo", -1)


if __name__ == "__main__":
    unittest.main()
