from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

MODULE_FILES = {
    "2": (("activity_tool.py", "src/travel_buddy/tools.py"),),
    "3": (
        ("agents_step.py", "src/travel_buddy/agents.py"),
        ("workflow_step.py", "src/travel_buddy/workflow.py"),
    ),
}
MODULE_FOLDERS = {"2": "01-tools", "3": "02-orchestration"}


@dataclass(frozen=True)
class RestoreOperation:
    source: Path
    destination: Path


def checkpoint_plan(
    root: str | Path,
    module: str,
    *,
    variant: str,
) -> list[RestoreOperation]:
    if variant not in {"starter", "solution"}:
        raise ValueError("Checkpoint variant must be starter or solution")
    try:
        files = MODULE_FILES[module]
        folder = MODULE_FOLDERS[module]
    except KeyError as exc:
        raise ValueError("Checkpoints are available only for modules 2 and 3") from exc
    repository = Path(root)
    operations = []
    for checkpoint_name, destination_relative in files:
        source = repository / "checkpoints" / folder / variant / checkpoint_name
        destination = repository / destination_relative
        if not source.is_file():
            raise FileNotFoundError(f"Checkpoint source not found: {source}")
        operations.append(RestoreOperation(source=source, destination=destination))
    return operations


def start_plan(root: str | Path, module: str) -> list[RestoreOperation]:
    return checkpoint_plan(root, module, variant="starter")


def restore_plan(root: str | Path, module: str) -> list[RestoreOperation]:
    return checkpoint_plan(root, module, variant="solution")


def apply_restore(operations: list[RestoreOperation], *, dry_run: bool) -> list[Path]:
    destinations = []
    for operation in operations:
        destinations.append(operation.destination)
        if not dry_run:
            operation.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(operation.source, operation.destination)
    return destinations
