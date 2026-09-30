import tempfile
import unittest
from pathlib import Path

from travel_buddy.evaluation import EvaluationCase, evaluate_text, load_cases, pass_rate


class EvaluationTests(unittest.TestCase):
    def test_repository_dataset_has_eight_cases(self) -> None:
        path = Path(__file__).parents[1] / "evaluations" / "travel_buddy_cases.jsonl"
        cases = load_cases(path)
        self.assertEqual(8, len(cases))
        self.assertEqual(8, len({case.case_id for case in cases}))

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

    def test_pass_rate_requires_results(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one"):
            pass_rate([])


if __name__ == "__main__":
    unittest.main()
