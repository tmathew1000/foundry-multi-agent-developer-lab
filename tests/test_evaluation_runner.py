import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from travel_buddy.cloud_evaluation import (
    build_testing_criteria,
    evaluation_rows,
    load_result,
    validate_comparison,
)
from travel_buddy.verification import module_checks

ROOT = Path(__file__).parents[1]
RUN = runpy.run_path(str(ROOT / "scripts" / "run_evaluation.py"))["run"]


class EvaluationRunnerTests(unittest.TestCase):
    def test_mocked_pair_preserves_baseline_and_marks_tool_evidence_unverified(self) -> None:
        dataset = ROOT / "evaluations" / "travel_buddy_cases.jsonl"
        items = [
            {
                "datasource_item": row,
                "sample": {"output_text": " ".join(row["required_terms"])},
                "results": [{"name": "task_completion", "score": 1.0, "passed": True}],
            }
            for row in evaluation_rows(dataset)
        ]
        version = {"value": "1"}
        runs = SimpleNamespace(
            create=Mock(return_value=SimpleNamespace(id="run-1", status="completed")),
            output_items=SimpleNamespace(list=Mock(return_value=items)),
            retrieve=Mock(),
            cancel=Mock(),
        )
        evals = SimpleNamespace(
            create=Mock(return_value=SimpleNamespace(id="eval-1")),
            retrieve=Mock(
                return_value={"testing_criteria": build_testing_criteria("travel-model")}
            ),
            runs=runs,
        )
        project = SimpleNamespace(
            agents=SimpleNamespace(
                list=lambda **_: [SimpleNamespace(name="travel-buddy")],
                get_version=lambda **_: SimpleNamespace(
                    name="travel-buddy", version=version["value"]
                ),
            ),
            get_openai_client=lambda: SimpleNamespace(evals=evals),
        )
        modules = {
            "dotenv": SimpleNamespace(load_dotenv=Mock()),
            "azure.ai.projects": SimpleNamespace(AIProjectClient=lambda **_: project),
            "azure.identity": SimpleNamespace(DefaultAzureCredential=lambda: object()),
            "openai": SimpleNamespace(APIError=type("APIError", (Exception,), {})),
        }
        environment = {
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.test/project",
            "AGENT_TRAVEL_BUDDY_NAME": "travel-buddy",
            "AGENT_TRAVEL_BUDDY_VERSION": "1",
            "AZURE_AI_MODEL_DEPLOYMENT_NAME": "travel-model",
        }
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict(sys.modules, modules),
            patch.dict(os.environ, environment, clear=True),
        ):
            args = SimpleNamespace(
                label="baseline",
                eval_id=None,
                dataset=dataset,
                results_dir=Path(folder),
                timeout=1.0,
                poll_interval=0.0,
            )
            baseline_path = RUN(args)
            original = baseline_path.read_bytes()
            with self.assertRaisesRegex(FileExistsError, "Refusing to overwrite"):
                RUN(args)
            args.label = "candidate"
            with self.assertRaisesRegex(ValueError, "distinct"):
                RUN(args)
            self.assertEqual(1, runs.create.call_count)
            os.environ["AGENT_TRAVEL_BUDDY_VERSION"] = "2"
            version["value"] = "2"
            args.eval_id = "other-eval"
            with self.assertRaisesRegex(ValueError, "--eval-id"):
                RUN(args)
            self.assertEqual(1, runs.create.call_count)
            args.eval_id = None
            original_criteria = evals.retrieve.return_value
            evals.retrieve.return_value = {
                "testing_criteria": build_testing_criteria("different-judge")
            }
            with self.assertRaisesRegex(ValueError, "actual_criteria_sha256"):
                RUN(args)
            self.assertEqual(1, runs.create.call_count)
            evals.retrieve.return_value = original_criteria
            candidate_path = RUN(args)
            self.assertEqual(original, baseline_path.read_bytes())
            baseline, candidate = load_result(baseline_path), load_result(candidate_path)
            self.assertIn("Live", validate_comparison(baseline, candidate))
            self.assertTrue(module_checks(ROOT, "5", results_dir=Path(folder))[0][1]())
            self.assertEqual("unverified", candidate["tool_execution_evidence"]["status"])
            self.assertEqual(12, len(candidate["tool_execution_evidence"]["case_ids"]))
            self.assertEqual(1, evals.create.call_count)
            self.assertEqual(2, runs.create.call_count)
            for call in runs.create.call_args_list:
                self.assertEqual("eval-1", call.kwargs["eval_id"])
            first, second = [call.kwargs["data_source"] for call in runs.create.call_args_list]
            self.assertEqual(first["source"], second["source"])
            self.assertEqual("1", first["target"]["version"])
            self.assertEqual("2", second["target"]["version"])

    def test_comparison_cli_labels_fallback_and_missing_scores(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            for label, score in (("baseline", None), ("candidate", 1.0)):
                from travel_buddy.cloud_evaluation import write_result

                write_result(
                    Path(folder) / f"{label}.json",
                    {
                        "artifact_kind": "fallback",
                        "metrics": {"tool_success": {"average_score": score}},
                    },
                )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "compare_evaluations.py"),
                    "baseline",
                    "candidate",
                    "--results-dir",
                    folder,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("Illustrative", completed.stdout)
            self.assertIn("unverified", completed.stdout)

    def test_comparison_cli_does_not_silently_use_fallback_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "compare_evaluations.py"),
                    "baseline",
                    "candidate",
                    "--results-dir",
                    folder,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("Evaluation result not found", completed.stderr)


if __name__ == "__main__":
    unittest.main()
