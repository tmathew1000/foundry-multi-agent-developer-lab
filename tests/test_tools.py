import unittest

from mcp_server.catalog import search_activities
from travel_buddy.tools import convert_currency, estimate_trip_total, search_hotels


class ToolTests(unittest.TestCase):
    def test_currency_conversion_normalizes_codes_and_converts_through_usd(self) -> None:
        result = convert_currency(200, "eur", "jpy")

        self.assertEqual("ok", result["status"])
        self.assertEqual("EUR", result["input_currency"])
        self.assertEqual("JPY", result["output_currency"])
        self.assertEqual(32608.7, result["output_amount"])
        self.assertEqual(163.043478, result["rate"])
        self.assertIn("Workshop exchange rates", result["notice"])

    def test_currency_conversion_returns_explicit_unsupported_code_result(self) -> None:
        result = convert_currency(200, "CAD", "JPY")

        self.assertEqual("unsupported_currency", result["status"])
        self.assertEqual(["CAD"], result["unsupported_codes"])
        self.assertIsNone(result["output_amount"])
        self.assertIsNone(result["rate"])
        self.assertIn("CAD", result["error"])

    def test_currency_conversion_rejects_negative_amount(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            convert_currency(-1, "USD", "EUR")

    def test_hotel_total_scales_with_nights(self) -> None:
        options = search_hotels("Lisbon", "2027-06-02", 3)
        self.assertEqual(495, options[0]["price_usd"])

    def test_trip_total_rejects_negative_costs(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            estimate_trip_total(100, -1, 50)

    def test_activity_search_filters_interest_and_budget(self) -> None:
        results = search_activities("Mexico City", ["food"], 60)
        self.assertEqual(["Local food market tour"], [item["name"] for item in results])


if __name__ == "__main__":
    unittest.main()
