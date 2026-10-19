import tempfile
import unittest
from pathlib import Path

from travel_buddy.cloud_evaluation import evaluation_rows
from travel_buddy.evaluation import EvaluationCase, evaluate_text, load_cases, pass_rate


class EvaluationTests(unittest.TestCase):
    def test_repository_dataset_has_twelve_cases(self) -> None:
        path = Path(__file__).parents[1] / "evaluations" / "travel_buddy_cases.jsonl"
        cases = load_cases(path)
        self.assertEqual(12, len(cases))
        self.assertEqual(12, len({case.case_id for case in cases}))

    def test_currency_and_regression_scenarios_are_in_the_same_suite(self) -> None:
        path = Path(__file__).parents[1] / "evaluations" / "travel_buddy_cases.jsonl"
        rows = {row["case_id"]: row for row in evaluation_rows(path)}
        self.assertEqual(["Flights"], rows["currency-supported"]["expected_agents"])
        self.assertEqual(["Flights"], rows["currency-unsupported-cad"]["expected_agents"])
        self.assertEqual(["Hotels"], rows["hotel-only"]["expected_agents"])
        self.assertEqual(
            ["Flights", "Hotels", "Activities"], rows["complete-itinerary"]["expected_agents"]
        )
        cases = {case.case_id: case for case in load_cases(path)}
        self.assertTrue(
            evaluate_text(
                cases["currency-supported"], "200 EUR converts to 32608.70 JPY at workshop rates."
            ).passed
        )
        self.assertTrue(
            evaluate_text(
                cases["currency-unsupported-cad"], "CAD is unsupported by the workshop tool."
            ).passed
        )
        self.assertFalse(
            evaluate_text(
                cases["currency-unsupported-cad"], "Approximately 21,000 JPY at a rough rate."
            ).passed
        )

    def test_text_evaluator_reports_missing_and_forbidden_terms(self) -> None:
        case = EvaluationCase(
            "safety",
            "query",
            ("Coordinator",),
            ("assumption",),
            ("booked",),
        )
        result = evaluate_text(case, "Your trip is booked.")
        self.assertFalse(result.passed)
        self.assertEqual(("assumption",), result.missing_terms)
        self.assertEqual(("booked",), result.present_forbidden_terms)

    def test_invalid_jsonl_reports_line(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cases.jsonl"
            path.write_text('{"case_id": "missing-fields"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 1"):
                load_cases(path)

    def test_evaluation_rows_reject_duplicate_ids_and_oversized_suites(self) -> None:
        repository_dataset = Path(__file__).parents[1] / "evaluations" / "travel_buddy_cases.jsonl"
        first = repository_dataset.read_text(encoding="utf-8").splitlines()[0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "cases.jsonl"
            path.write_text((first + "\n") * 6, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique"):
                evaluation_rows(path)
            path.write_text((first + "\n") * 13, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "6-12"):
                evaluation_rows(path)

    def test_pass_rate_requires_results(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one"):
            pass_rate([])


if __name__ == "__main__":
    unittest.main()
