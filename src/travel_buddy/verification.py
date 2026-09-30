from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

MODULE_IDENTIFIERS = ("0", "1", "2", "3", "4", "5")


def normalize_module_identifier(identifier: str) -> tuple[str, ...]:
    normalized = identifier.casefold()
    if normalized == "all":
        return MODULE_IDENTIFIERS
    if normalized not in MODULE_IDENTIFIERS:
        raise ValueError("module must be 0-5 or all")
    return (normalized,)


def module_checks(root: Path, module: str) -> list[tuple[str, Callable[[], bool]]]:
    def result_file(label: str) -> Path:
        generated = root / ".foundry" / "results" / f"{label}.json"
        if generated.is_file():
            return generated
        return root / "artifacts" / "evaluations" / f"{label}.json"

    checks: dict[str, list[tuple[str, Callable[[], bool]]]] = {
        "0": [
            ("project configuration", lambda: (root / "azure.yaml").is_file()),
            ("MCP container", lambda: (root / "src/mcp_server/Dockerfile").is_file()),
        ],
        "1": [
            ("hosted entry point", lambda: (root / "main.py").is_file()),
            ("TravelBuddy package", lambda: (root / "src/travel_buddy/__init__.py").is_file()),
        ],
        "2": [
            ("function tools", lambda: (root / "src/travel_buddy/tools.py").is_file()),
            ("MCP server", lambda: (root / "src/mcp_server/server.py").is_file()),
            (
                "grounding configuration",
                lambda: (root / "src/travel_buddy/integrations.py").is_file(),
            ),
        ],
        "3": [
            (
                "Coordinator registered",
                lambda: _contains(root / "src/travel_buddy/agents.py", 'name="Coordinator"'),
            ),
            (
                "FlightsSpecialist registered",
                lambda: _contains(root / "src/travel_buddy/agents.py", 'name="Flights"'),
            ),
            (
                "HotelsSpecialist registered",
                lambda: _contains(root / "src/travel_buddy/agents.py", 'name="Hotels"'),
            ),
            (
                "ActivitiesSpecialist registered",
                lambda: _contains(root / "src/travel_buddy/agents.py", 'name="Activities"'),
            ),
            (
                "Workflow exposed as an agent",
                lambda: _contains(root / "src/travel_buddy/workflow.py", "workflow.as_agent"),
            ),
        ],
        "4": [
            (
                "tracing configuration is present",
                lambda: _contains(
                    root / "src/travel_buddy/observability.py",
                    "configure_azure_monitor",
                ),
            ),
        ],
        "5": [
            (
                "baseline and candidate results are comparable",
                lambda: _comparable(result_file("baseline"), result_file("candidate")),
            ),
        ],
    }
    return checks[module]


def _contains(path: Path, text: str) -> bool:
    return path.is_file() and text in path.read_text(encoding="utf-8")


def _comparable(baseline: Path, candidate: Path) -> bool:
    if not baseline.is_file() or not candidate.is_file():
        return False
    from .cloud_evaluation import compare_metrics, load_result

    return bool(compare_metrics(load_result(baseline), load_result(candidate)))
