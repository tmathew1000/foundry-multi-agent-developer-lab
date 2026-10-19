from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ConfigurationError, resolve_model_deployment
from .evaluation import load_cases

COMPARISON_LABELS = ("baseline", "candidate")
TERMINAL_STATUSES = {"completed", "failed", "canceled"}
MIN_EVALUATION_CASES = 6
MAX_EVALUATION_CASES = 12
INVOCATION_STATE_POLICY = "service-managed target completions; no conversation IDs supplied"


class EvaluationConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class HostedAgentEvaluationConfig:
    project_endpoint: str
    agent_name: str
    agent_version: str
    judge_model: str

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> HostedAgentEvaluationConfig:
        values = os.environ if env is None else env
        try:
            judge_model = resolve_model_deployment(values)
        except ConfigurationError as exc:
            raise EvaluationConfigurationError(str(exc)) from exc
        resolved = {
            "project_endpoint": values.get("FOUNDRY_PROJECT_ENDPOINT")
            or values.get("AZURE_AI_PROJECT_ENDPOINT"),
            "agent_name": values.get("FOUNDRY_AGENT_NAME") or values.get("AGENT_TRAVEL_BUDDY_NAME"),
            "agent_version": values.get("FOUNDRY_AGENT_VERSION")
            or values.get("AGENT_TRAVEL_BUDDY_VERSION"),
            "judge_model": judge_model,
        }
        missing = [name for name, value in resolved.items() if not value]
        if missing:
            raise EvaluationConfigurationError(
                "Missing evaluation configuration: " + ", ".join(missing)
            )
        return cls(
            project_endpoint=str(resolved["project_endpoint"]),
            agent_name=str(resolved["agent_name"]),
            agent_version=str(resolved["agent_version"]),
            judge_model=str(resolved["judge_model"]),
        )


def validate_label(label: str) -> str:
    if label not in COMPARISON_LABELS:
        raise ValueError(f"label must be one of: {', '.join(COMPARISON_LABELS)}")
    return label


def build_data_source(
    rows: Iterable[Mapping[str, Any]],
    config: HostedAgentEvaluationConfig,
) -> dict[str, Any]:
    content = [{"item": dict(row)} for row in rows]
    return {
        "type": "azure_ai_target_completions",
        "source": {"type": "file_content", "content": content},
        "target": {
            "type": "azure_ai_agent",
            "name": config.agent_name,
            "version": config.agent_version,
        },
    }


def build_testing_criteria(judge_model: str) -> list[dict[str, Any]]:
    names = (
        ("task_completion", "builtin.task_completion"),
        ("tool_selection", "builtin.tool_selection"),
        ("tool_success", "builtin.tool_call_success"),
        ("groundedness", "builtin.groundedness"),
    )
    return [
        {
            "type": "azure_ai_evaluator",
            "name": name,
            "evaluator_name": evaluator_name,
            "initialization_parameters": {"deployment_name": judge_model},
        }
        for name, evaluator_name in names
    ]


def evaluation_rows(path: str | Path) -> list[dict[str, Any]]:
    cases = load_cases(path)
    if not MIN_EVALUATION_CASES <= len(cases) <= MAX_EVALUATION_CASES:
        raise ValueError(
            f"Expected {MIN_EVALUATION_CASES}-{MAX_EVALUATION_CASES} evaluation rows, "
            f"received {len(cases)}"
        )
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Evaluation case IDs must be unique")
    return [
        {
            "case_id": case.case_id,
            "query": case.query,
            "expected_agents": list(case.expected_agents),
            "required_terms": list(case.required_terms),
            "forbidden_terms": list(case.forbidden_terms),
        }
        for case in cases
    ]


def build_provenance(
    rows: list[dict[str, Any]],
    config: HostedAgentEvaluationConfig,
) -> dict[str, Any]:
    return {
        "dataset_sha256": _fingerprint(rows),
        "requested_criteria_sha256": _fingerprint(build_testing_criteria(config.judge_model)),
        "project_endpoint": config.project_endpoint,
        "agent_name": config.agent_name,
        "invocation_state_policy": INVOCATION_STATE_POLICY,
    }


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_candidate_inputs(
    baseline: Mapping[str, Any],
    provenance: Mapping[str, Any],
    config: HostedAgentEvaluationConfig,
) -> None:
    previous = baseline.get("provenance")
    if baseline.get("artifact_kind") == "fallback" or not isinstance(previous, Mapping):
        raise ValueError(
            "A live baseline with provenance is required; archive old results and rerun."
        )
    for key, value in provenance.items():
        if previous.get(key) != value:
            raise ValueError(
                f"Baseline and candidate differ in {key}; do not compare different suites."
            )
    agent = baseline.get("agent")
    if not isinstance(agent, Mapping) or agent.get("name") != config.agent_name:
        raise ValueError("Baseline and candidate must target the same agent.")
    if not agent.get("version") or str(agent["version"]) == config.agent_version:
        raise ValueError("Deploy a distinct candidate agent version after capturing the baseline.")


def validate_comparison(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> str:
    fallback = [item.get("artifact_kind") == "fallback" for item in (baseline, candidate)]
    if any(fallback):
        if not all(fallback):
            raise ValueError("Do not mix illustrative fallback results with live results.")
        return "Illustrative fallback comparison only; not evidence from your deployment."
    required = (
        "dataset_sha256",
        "requested_criteria_sha256",
        "actual_criteria_sha256",
        "project_endpoint",
        "agent_name",
        "invocation_state_policy",
    )
    provenance = baseline.get("provenance")
    other = candidate.get("provenance")
    if not isinstance(provenance, Mapping) or not isinstance(other, Mapping):
        raise ValueError("Live comparison requires provenance; archive old results and rerun both.")
    for key in required:
        if not provenance.get(key) or provenance[key] != other.get(key):
            raise ValueError(f"Missing or mismatched comparison provenance: {key}")
    first_agent = baseline.get("agent", {})
    second_agent = candidate.get("agent", {})
    if not isinstance(first_agent, Mapping) or not isinstance(second_agent, Mapping):
        raise ValueError("Comparison requires recorded agent identities.")
    versions = [item.get("version") for item in (first_agent, second_agent)]
    if (
        not all(versions)
        or str(versions[0]) == str(versions[1])
        or any(item.get("name") != provenance["agent_name"] for item in (first_agent, second_agent))
    ):
        raise ValueError("Comparison requires the same agent with two distinct recorded versions.")
    first_eval = baseline.get("evaluation", {})
    second_eval = candidate.get("evaluation", {})
    if (
        not isinstance(first_eval, Mapping)
        or not isinstance(second_eval, Mapping)
        or not first_eval.get("id")
        or first_eval["id"] != second_eval.get("id")
    ):
        raise ValueError("Baseline and candidate must reuse the same evaluation definition.")
    return (
        "Live version comparison; tool execution and conversation isolation "
        "need trace verification."
    )


def record_actual_criteria(provenance: dict[str, Any], definition: Any) -> None:
    criteria = _get_value(definition, "testing_criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("Evaluation definition did not return testing_criteria.")
    provenance["actual_criteria_sha256"] = _fingerprint([_to_dict(item) for item in criteria])


def poll_run(
    retrieve: Callable[[], Any],
    cancel: Callable[[], Any],
    initial_run: Any,
    *,
    timeout_seconds: float,
    poll_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> Any:
    run = initial_run
    deadline = monotonic() + timeout_seconds
    while run.status not in TERMINAL_STATUSES:
        if monotonic() >= deadline:
            cancel()
            raise TimeoutError(f"Evaluation run {run.id} exceeded {timeout_seconds} seconds")
        sleep(poll_seconds)
        run = retrieve()
    if run.status != "completed":
        error = _to_dict(getattr(run, "error", None))
        raise RuntimeError(f"Evaluation run {run.id} ended in {run.status}: {error}")
    return run


def summarize_output_items(items: Iterable[Any]) -> dict[str, dict[str, float | int | None]]:
    accumulators: dict[str, dict[str, float | int]] = {}
    for item in items:
        for result in _get_value(item, "results", []):
            name = str(_get_value(result, "name", "unknown"))
            score = _get_value(result, "score")
            passed = _get_value(result, "passed")
            current = accumulators.setdefault(
                name,
                {"count": 0, "score_total": 0.0, "score_count": 0, "passed": 0},
            )
            current["count"] = int(current["count"]) + 1
            if _numeric_score(score) is not None:
                current["score_total"] = float(current["score_total"]) + float(score)
                current["score_count"] = int(current["score_count"]) + 1
            if passed is True:
                current["passed"] = int(current["passed"]) + 1

    summary: dict[str, dict[str, float | int | None]] = {}
    for name, values in accumulators.items():
        count = int(values["count"])
        score_count = int(values["score_count"])
        summary[name] = {
            "count": count,
            "score_count": score_count,
            "average_score": (float(values["score_total"]) / score_count if score_count else None),
            "pass_rate": float(values["passed"]) / count if count else 0.0,
        }
    return summary


def summarize_response_contract(
    items: Iterable[Any],
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, float | int]:
    expected = {str(row["case_id"]): row for row in rows}
    results = []
    seen: set[str] = set()
    for item in items:
        payload = _to_dict(item)
        datasource = _get_value(payload, "datasource_item", {})
        datasource = _get_value(datasource, "item", datasource)
        case_id = str(_get_value(datasource, "case_id", ""))
        if case_id not in expected:
            raise RuntimeError(f"Evaluation output has unknown case_id: {case_id!r}")
        if case_id in seen:
            raise RuntimeError(f"Evaluation output has duplicate case_id: {case_id!r}")
        seen.add(case_id)
        sample = _get_value(payload, "sample", {})
        response = _get_value(sample, "output_text")
        if not isinstance(response, str):
            raise RuntimeError(f"Evaluation output for {case_id!r} has no sample.output_text")
        row = expected[case_id]
        normalized = response.casefold()
        required = [str(term).casefold() for term in row.get("required_terms", [])]
        forbidden = [str(term).casefold() for term in row.get("forbidden_terms", [])]
        passed = all(term in normalized for term in required) and not any(
            term in normalized for term in forbidden
        )
        results.append(passed)

    if len(results) != len(expected):
        raise RuntimeError(
            f"Expected {len(expected)} response-contract outputs, received {len(results)}"
        )
    passed_count = sum(results)
    return {
        "count": len(results),
        "average_score": passed_count / len(results),
        "pass_rate": passed_count / len(results),
    }


def write_result(path: str | Path, payload: Mapping[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_result(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Evaluation result not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Evaluation result is not valid JSON: {source}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("metrics"), dict):
        raise ValueError(f"Evaluation result has no metrics object: {source}")
    return payload


def compare_metrics(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> list[dict[str, float | str | None]]:
    baseline_metrics = baseline.get("metrics", {})
    candidate_metrics = candidate.get("metrics", {})
    if not isinstance(baseline_metrics, Mapping) or not isinstance(candidate_metrics, Mapping):
        raise ValueError("Both evaluation results must contain metrics")
    names = sorted(set(baseline_metrics) | set(candidate_metrics))
    if not names:
        raise ValueError("Evaluation results contain no comparable metrics")
    rows = []
    for name in names:
        baseline_score = _metric_score(baseline_metrics.get(name))
        candidate_score = _metric_score(candidate_metrics.get(name))
        rows.append(
            {
                "metric": str(name),
                "baseline": baseline_score,
                "candidate": candidate_score,
                "change": (
                    candidate_score - baseline_score
                    if candidate_score is not None and baseline_score is not None
                    else None
                ),
            }
        )
    return rows


def _metric_score(value: Any) -> float | None:
    if not isinstance(value, Mapping):
        return None
    return _numeric_score(value.get("average_score"))


def _numeric_score(score: Any) -> float | None:
    if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score):
        return float(score)
    return None


def _get_value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _to_dict(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return dict(value)
    converter = getattr(value, "to_dict", None)
    return converter() if callable(converter) else str(value)
