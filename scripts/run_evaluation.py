from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from travel_buddy.cloud_evaluation import (
    HostedAgentEvaluationConfig,
    build_data_source,
    build_provenance,
    build_testing_criteria,
    evaluation_rows,
    poll_run,
    record_actual_criteria,
    summarize_output_items,
    summarize_response_contract,
    validate_candidate_inputs,
    validate_label,
    write_result,
)


def _serialize(value: Any) -> Any:
    converter = getattr(value, "to_dict", None)
    return converter() if callable(converter) else value


def run(args: argparse.Namespace) -> Path:
    label = validate_label(args.label)
    root = Path(__file__).parents[1]
    destination = args.results_dir / f"{label}.json"
    if destination.exists():
        raise FileExistsError(
            f"Refusing to overwrite {destination}; archive the pair or use a new --results-dir."
        )
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError("Install project dependencies before running evaluations") from exc
    load_dotenv(root / ".env")
    config = HostedAgentEvaluationConfig.from_env()
    rows = evaluation_rows(args.dataset)
    provenance = build_provenance(rows, config)
    baseline = None
    eval_id = args.eval_id
    if label == "candidate":
        baseline_path = args.results_dir / "baseline.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        validate_candidate_inputs(baseline, provenance, config)
        baseline_eval_id = baseline.get("evaluation", {}).get("id")
        if not isinstance(baseline_eval_id, str) or not baseline_eval_id:
            raise ValueError(f"Baseline result has no evaluation id: {baseline_path}")
        if eval_id is not None and eval_id != baseline_eval_id:
            raise ValueError("--eval-id must match the baseline evaluation definition.")
        eval_id = baseline_eval_id

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

        definition = client.evals.retrieve(eval_id)
        record_actual_criteria(provenance, definition)
        if baseline is not None:
            validate_candidate_inputs(baseline, provenance, config)

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
        "schema_version": 2,
        "label": label,
        "agent": {"name": config.agent_name, "version": config.agent_version},
        "evaluation": {"id": eval_id, "run_id": completed.id},
        "provenance": provenance,
        "tool_execution_evidence": {
            "status": "unverified",
            "case_ids": [row["case_id"] for row in rows],
            "notice": (
                "Response terms and expected_agents do not prove tool execution. "
                "Inspect per-case traces and conversation isolation manually."
            ),
        },
        "run": _serialize(completed),
        "metrics": metrics,
        "output_items": [_serialize(item) for item in output_items],
    }
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
    parser.add_argument("--results-dir", type=Path, default=root / ".foundry" / "results")
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
