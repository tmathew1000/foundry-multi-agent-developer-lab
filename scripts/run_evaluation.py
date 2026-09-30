from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from travel_buddy.cloud_evaluation import (
    HostedAgentEvaluationConfig,
    build_data_source,
    build_testing_criteria,
    evaluation_rows,
    poll_run,
    summarize_output_items,
    summarize_response_contract,
    validate_label,
    write_result,
)


def _serialize(value: Any) -> Any:
    converter = getattr(value, "to_dict", None)
    return converter() if callable(converter) else value


def _existing_eval_id(root: Path, label: str, explicit_eval_id: str | None) -> str | None:
    if explicit_eval_id:
        return explicit_eval_id
    if label != "candidate":
        return None
    baseline_path = root / ".foundry" / "results" / "baseline.json"
    if not baseline_path.is_file():
        raise FileNotFoundError(
            "Candidate evaluation requires .foundry/results/baseline.json or --eval-id"
        )
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    try:
        return str(baseline["evaluation"]["id"])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Baseline result has no evaluation id: {baseline_path}") from exc


def run(args: argparse.Namespace) -> Path:
    label = validate_label(args.label)
    root = Path(__file__).parents[1]
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("Install project dependencies before running evaluations") from exc
    load_dotenv(root / ".env")
    config = HostedAgentEvaluationConfig.from_env()
    rows = evaluation_rows(args.dataset)

    try:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
        from openai import APIError
    except ImportError as exc:
        raise RuntimeError("Install project dependencies before running evaluations") from exc

    try:
        project_client = AIProjectClient(
            endpoint=config.project_endpoint,
            credential=DefaultAzureCredential(),
        )
        hosted_names = {agent.name for agent in project_client.agents.list(kind="hosted")}
        if config.agent_name not in hosted_names:
            raise LookupError(
                f"{config.agent_name!r} is not a deployed hosted agent in this project"
            )
        agent = project_client.agents.get_version(
            agent_name=config.agent_name,
            agent_version=config.agent_version,
        )
        if agent.name != config.agent_name or str(agent.version) != config.agent_version:
            raise RuntimeError(
                f"Resolved unexpected agent identity: {agent.name!r} v{agent.version!r}"
            )

        client = project_client.get_openai_client()
        eval_id = _existing_eval_id(root, label, args.eval_id)
        if eval_id is None:
            definition = client.evals.create(
                name=f"TravelBuddy hosted-agent quality - {config.agent_name}",
                data_source_config={
                    "type": "azure_ai_source",
                    "scenario": "target_completions",
                },
                testing_criteria=build_testing_criteria(config.judge_model),
            )
            eval_id = definition.id

        created = client.evals.runs.create(
            eval_id=eval_id,
            name=f"{label} - {config.agent_name} - v{config.agent_version}",
            metadata={
                "comparison_role": label,
                "agent_name": config.agent_name,
                "agent_version": config.agent_version,
            },
            data_source=build_data_source(rows, config),
        )
        completed = poll_run(
            lambda: client.evals.runs.retrieve(run_id=created.id, eval_id=eval_id),
            lambda: client.evals.runs.cancel(run_id=created.id, eval_id=eval_id),
            created,
            timeout_seconds=args.timeout,
            poll_seconds=args.poll_interval,
        )
        output_items = list(client.evals.runs.output_items.list(run_id=created.id, eval_id=eval_id))
    except APIError as exc:
        raise RuntimeError(f"Foundry/OpenAI evaluation API failure: {exc}") from exc

    if len(output_items) != len(rows):
        raise RuntimeError(f"Expected {len(rows)} evaluation outputs, received {len(output_items)}")
    metrics = summarize_output_items(output_items)
    metrics["response_contract"] = summarize_response_contract(output_items, rows)
    payload = {
        "schema_version": 1,
        "label": label,
        "agent": {"name": config.agent_name, "version": config.agent_version},
        "evaluation": {"id": eval_id, "run_id": completed.id},
        "run": _serialize(completed),
        "metrics": metrics,
        "output_items": [_serialize(item) for item in output_items],
    }
    destination = root / ".foundry" / "results" / f"{label}.json"
    return write_result(destination, payload)


def main() -> int:
    root = Path(__file__).parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, choices=["baseline", "candidate"])
    parser.add_argument(
        "--dataset",
        type=Path,
        default=root / "evaluations" / "travel_buddy_cases.jsonl",
    )
    parser.add_argument("--eval-id")
    parser.add_argument("--timeout", type=float, default=1200.0)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    args = parser.parse_args()
    try:
        destination = run(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
