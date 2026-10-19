import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from travel_buddy.cloud_evaluation import (
    EvaluationConfigurationError,
    HostedAgentEvaluationConfig,
    build_data_source,
    build_provenance,
    build_testing_criteria,
    compare_metrics,
    load_result,
    poll_run,
    record_actual_criteria,
    summarize_output_items,
    summarize_response_contract,
    validate_candidate_inputs,
    validate_comparison,
    validate_label,
    write_result,
)


class CloudEvaluationHelperTests(unittest.TestCase):
    def result_pair(self):
        config = HostedAgentEvaluationConfig("endpoint", "travel-buddy", "1", "model")
        provenance = build_provenance([{"case_id": "case-1", "query": "query"}], config)
        record_actual_criteria(
            provenance, {"testing_criteria": build_testing_criteria(config.judge_model)}
        )
        baseline = {
            "agent": {"name": config.agent_name, "version": "1"},
            "evaluation": {"id": "eval-1"},
            "provenance": provenance,
        }
        candidate = {
            **baseline,
            "agent": {"name": config.agent_name, "version": "2"},
            "provenance": dict(provenance),
        }
        return baseline, candidate

    def test_comparison_requires_same_suite_settings_and_distinct_versions(self) -> None:
        baseline, candidate = self.result_pair()
        self.assertIn("Live version comparison", validate_comparison(baseline, candidate))
        for key in baseline["provenance"]:
            with self.subTest(changed=key):
                changed = {
                    **candidate,
                    "provenance": {**candidate["provenance"], key: "different"},
                }
                with self.assertRaisesRegex(ValueError, "provenance"):
                    validate_comparison(baseline, changed)
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_comparison(baseline, {**candidate, "agent": baseline["agent"]})
        with self.assertRaisesRegex(ValueError, "evaluation definition"):
            validate_comparison(baseline, {**candidate, "evaluation": {"id": "other"}})
        with self.assertRaisesRegex(ValueError, "requires provenance"):
            validate_comparison({"metrics": {}}, {"metrics": {}})

    def test_candidate_inputs_reject_changed_cases_assertions_judge_and_version(self) -> None:
        config = HostedAgentEvaluationConfig("endpoint", "travel-buddy", "2", "model")
        rows = [{"case_id": "case-1", "query": "query", "required_terms": ["CAD"]}]
        baseline = {
            "agent": {"name": "travel-buddy", "version": "1"},
            "provenance": build_provenance(rows, config),
        }
        validate_candidate_inputs(baseline, build_provenance(rows, config), config)
        for change in ({"query": "different"}, {"required_terms": ["unsupported"]}):
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, "dataset_sha256"):
                    validate_candidate_inputs(
                        baseline, build_provenance([{**rows[0], **change}], config), config
                    )
        other_judge = HostedAgentEvaluationConfig("endpoint", "travel-buddy", "2", "other")
        with self.assertRaisesRegex(ValueError, "criteria"):
            validate_candidate_inputs(baseline, build_provenance(rows, other_judge), other_judge)
        with self.assertRaisesRegex(ValueError, "distinct"):
            validate_candidate_inputs(
                baseline,
                build_provenance(rows, config),
                HostedAgentEvaluationConfig("endpoint", "travel-buddy", "1", "model"),
            )

    def test_fallback_is_explicit_and_cannot_mix_with_live_results(self) -> None:
        fallback = {"artifact_kind": "fallback"}
        self.assertIn("Illustrative", validate_comparison(fallback, fallback))
        baseline, candidate = self.result_pair()
        for first, second in ((baseline, fallback), (fallback, candidate)):
            with self.assertRaisesRegex(ValueError, "mix"):
                validate_comparison(first, second)

    def test_missing_scores_remain_unverified_not_zero(self) -> None:
        summary = summarize_output_items([{"results": [{"name": "tool_success", "passed": None}]}])
        self.assertIsNone(summary["tool_success"]["average_score"])
        self.assertEqual(0, summary["tool_success"]["score_count"])
        for missing in (None, True, float("nan"), float("inf")):
            with self.subTest(score=missing):
                rows = compare_metrics(
                    {"metrics": {"tool_success": {"average_score": missing}}},
                    {"metrics": {"tool_success": {"average_score": 1.0}}},
                )
                self.assertIsNone(rows[0]["baseline"])
                self.assertIsNone(rows[0]["change"])
        rows = compare_metrics(
            {"metrics": {"tool_success": {"average_score": 1.0}}},
            {"metrics": {"task_completion": {"average_score": 1.0}}},
        )
        self.assertTrue(all(row["change"] is None for row in rows))

    def test_response_wording_does_not_establish_tool_execution(self) -> None:
        rows = [
            {
                "case_id": "cad",
                "expected_agents": ["Flights"],
                "required_terms": ["CAD", "unsupported"],
                "forbidden_terms": [],
            }
        ]
        items = [
            {
                "datasource_item": {"case_id": "cad"},
                "sample": {"output_text": "CAD is unsupported."},
            }
        ]
        self.assertEqual(1.0, summarize_response_contract(items, rows)["pass_rate"])
        self.assertNotIn("tool_execution", summarize_response_contract(items, rows))
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            summarize_response_contract(items * 2, rows)

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

    def test_configuration_accepts_azd_model_deployment_metadata(self) -> None:
        config = HostedAgentEvaluationConfig.from_env(
            {
                "FOUNDRY_PROJECT_ENDPOINT": "https://example.test/project",
                "AGENT_TRAVEL_BUDDY_NAME": "travel-buddy",
                "AGENT_TRAVEL_BUDDY_VERSION": "7",
                "AI_PROJECT_DEPLOYMENTS": '[{"name":"travel-model"}]',
            }
        )

        self.assertEqual("travel-model", config.judge_model)

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
