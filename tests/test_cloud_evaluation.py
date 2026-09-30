import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from travel_buddy.cloud_evaluation import (
    EvaluationConfigurationError,
    HostedAgentEvaluationConfig,
    build_data_source,
    compare_metrics,
    load_result,
    poll_run,
    summarize_output_items,
    summarize_response_contract,
    validate_label,
    write_result,
)


class CloudEvaluationHelperTests(unittest.TestCase):
    def test_configuration_accepts_azd_agent_environment_names(self) -> None:
        config = HostedAgentEvaluationConfig.from_env(
            {
                "FOUNDRY_PROJECT_ENDPOINT": "https://example.test/project",
                "AGENT_TRAVEL_BUDDY_NAME": "travel-buddy",
                "AGENT_TRAVEL_BUDDY_VERSION": "7",
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": "travel-model",
            }
        )
        self.assertEqual("7", config.agent_version)

    def test_configuration_reports_all_missing_values(self) -> None:
        with self.assertRaisesRegex(
            EvaluationConfigurationError,
            "project_endpoint, agent_name, agent_version, judge_model",
        ):
            HostedAgentEvaluationConfig.from_env({})

    def test_data_source_targets_exact_agent_version(self) -> None:
        config = HostedAgentEvaluationConfig("endpoint", "travel-buddy", "4", "model")
        source = build_data_source([{"query": "Plan a trip"}], config)
        self.assertEqual(
            {"type": "azure_ai_agent", "name": "travel-buddy", "version": "4"},
            source["target"],
        )
        self.assertNotIn("input_messages", source)

    def test_target_evaluators_use_deployment_name_without_custom_mappings(self) -> None:
        from travel_buddy.cloud_evaluation import build_testing_criteria

        criteria = build_testing_criteria("travel-model")
        self.assertEqual(4, len(criteria))
        for item in criteria:
            self.assertEqual(
                {"deployment_name": "travel-model"},
                item["initialization_parameters"],
            )
            self.assertNotIn("data_mapping", item)

    def test_poll_run_cancels_on_timeout(self) -> None:
        canceled = []
        run = SimpleNamespace(id="run-1", status="queued")
        with self.assertRaises(TimeoutError):
            poll_run(
                lambda: run,
                lambda: canceled.append(True),
                run,
                timeout_seconds=0,
                poll_seconds=0,
                sleep=lambda _: None,
                monotonic=lambda: 1,
            )
        self.assertEqual([True], canceled)

    def test_metric_summary_and_comparison(self) -> None:
        items = [
            {
                "results": [
                    {"name": "task_completion", "score": 0.5, "passed": False},
                    {"name": "tool_success", "score": 1.0, "passed": True},
                ]
            },
            {"results": [{"name": "task_completion", "score": 1.0, "passed": True}]},
        ]
        baseline = {"metrics": summarize_output_items(items)}
        candidate = {
            "metrics": {
                **baseline["metrics"],
                "task_completion": {
                    "count": 2,
                    "average_score": 1.0,
                    "pass_rate": 1.0,
                },
            }
        }
        rows = compare_metrics(baseline, candidate)
        task = next(row for row in rows if row["metric"] == "task_completion")
        self.assertEqual(0.25, task["change"])

    def test_response_contract_uses_required_and_forbidden_terms(self) -> None:
        rows = [
            {
                "case_id": "case-1",
                "required_terms": ["flight"],
                "forbidden_terms": ["booked"],
            },
            {
                "case_id": "case-2",
                "required_terms": ["hotel"],
                "forbidden_terms": ["confirmed"],
            },
        ]
        items = [
            {
                "datasource_item": {"case_id": "case-1"},
                "sample": {"output_text": "Here is a flight option."},
            },
            {
                "datasource_item": {"item": {"case_id": "case-2"}},
                "sample": {"output_text": "Your hotel is confirmed."},
            },
        ]

        summary = summarize_response_contract(items, rows)

        self.assertEqual(2, summary["count"])
        self.assertEqual(0.5, summary["pass_rate"])

    def test_result_round_trip_and_label_validation(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "result.json"
            write_result(path, {"metrics": {"score": {"average_score": 1.0}}})
            self.assertEqual(1.0, load_result(path)["metrics"]["score"]["average_score"])
            self.assertTrue(path.read_text(encoding="utf-8").endswith("\n"))
        with self.assertRaises(ValueError):
            validate_label("experiment")


if __name__ == "__main__":
    unittest.main()
