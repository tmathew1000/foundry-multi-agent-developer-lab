from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    query: str
    expected_agents: tuple[str, ...]
    required_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    passed: bool
    missing_terms: tuple[str, ...]
    present_forbidden_terms: tuple[str, ...]


def load_cases(path: str | Path) -> list[EvaluationCase]:
    cases = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                cases.append(
                    EvaluationCase(
                        case_id=raw["case_id"],
                        query=raw["query"],
                        expected_agents=tuple(raw["expected_agents"]),
                        required_terms=tuple(raw.get("required_terms", [])),
                        forbidden_terms=tuple(raw.get("forbidden_terms", [])),
                    )
                )
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid evaluation case at line {line_number}") from exc
    return cases


def evaluate_text(case: EvaluationCase, response: str) -> EvaluationResult:
    normalized = response.casefold()
    missing = tuple(term for term in case.required_terms if term.casefold() not in normalized)
    forbidden = tuple(term for term in case.forbidden_terms if term.casefold() in normalized)
    return EvaluationResult(
        case_id=case.case_id,
        passed=not missing and not forbidden,
        missing_terms=missing,
        present_forbidden_terms=forbidden,
    )


def pass_rate(results: Iterable[EvaluationResult]) -> float:
    collected = list(results)
    if not collected:
        raise ValueError("At least one evaluation result is required")
    return sum(result.passed for result in collected) / len(collected)
