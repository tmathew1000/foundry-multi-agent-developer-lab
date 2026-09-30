from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evaluation import load_cases

COMPARISON_LABELS = ("baseline", "candidate")
TERMINAL_STATUSES = {"completed", "failed", "canceled"}


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
        resolved = {
            "project_endpoint": values.get("FOUNDRY_PROJECT_ENDPOINT")
            or values.get("AZURE_AI_PROJECT_ENDPOINT"),
            "agent_name": values.get("FOUNDRY_AGENT_NAME") or values.get("AGENT_TRAVEL_BUDDY_NAME"),
            "agent_version": values.get("FOUNDRY_AGENT_VERSION")
            or values.get("AGENT_TRAVEL_BUDDY_VERSION"),
            "judge_model": values.get("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
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
    if not 6 <= len(cases) <= 10:
        raise ValueError(f"Expected 6-10 evaluation rows, received {len(cases)}")
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


def summarize_output_items(items: Iterable[Any]) -> dict[str, dict[str, float | int]]:
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
            if isinstance(score, (int, float)):
                current["score_total"] = float(current["score_total"]) + float(score)
                current["score_count"] = int(current["score_count"]) + 1
            if passed is True:
                current["passed"] = int(current["passed"]) + 1

    summary: dict[str, dict[str, float | int]] = {}
    for name, values in accumulators.items():
        count = int(values["count"])
        score_count = int(values["score_count"])
        summary[name] = {
            "count": count,
            "average_score": (float(values["score_total"]) / score_count if score_count else 0.0),
            "pass_rate": float(values["passed"]) / count if count else 0.0,
        }
    return summary


def summarize_response_contract(
    items: Iterable[Any],
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, float | int]:
    expected = {str(row["case_id"]): row for row in rows}
    results = []
    for item in items:
        payload = _to_dict(item)
        datasource = _get_value(payload, "datasource_item", {})
        datasource = _get_value(datasource, "item", datasource)
        case_id = str(_get_value(datasource, "case_id", ""))
        if case_id not in expected:
            raise RuntimeError(f"Evaluation output has unknown case_id: {case_id!r}")
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
) -> list[dict[str, float | str]]:
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
                "change": candidate_score - baseline_score,
            }
        )
    return rows


def _metric_score(value: Any) -> float:
    if not isinstance(value, Mapping):
        return 0.0
    score = value.get("average_score")
    return float(score) if isinstance(score, (int, float)) else 0.0


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
