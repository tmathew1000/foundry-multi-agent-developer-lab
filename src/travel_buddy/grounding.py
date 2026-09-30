from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Any

from agent_framework import ContextProvider

DEFAULT_DESTINATIONS_PATH = Path(__file__).resolve().parents[2] / "data" / "destinations.json"


class DestinationGroundingProvider(ContextProvider):
    capability_metadata = {
        "kind": "local_curated_context_provider",
        "citation_format": "[source_id]",
        "limitations": (
            "Static workshop data with lexical retrieval; it is not live availability, "
            "booking data, or an Azure AI Search index."
        ),
    }

    def __init__(self, data_path: str | Path = DEFAULT_DESTINATIONS_PATH) -> None:
        super().__init__(source_id="travel_buddy.destination_grounding")
        self.data_path = _resolve_data_path(data_path)
        self._records = _load_destination_records(self.data_path)

    def retrieve_destination_context(
        self,
        query: Annotated[str, "Destination, neighborhood, lodging, or activity question"],
        limit: Annotated[int, "Maximum destination records to return"] = 3,
    ) -> dict[str, object]:
        if limit < 1:
            raise ValueError("limit must be at least 1")

        query_text = query.strip()
        if not query_text:
            raise ValueError("query cannot be empty")
        query_tokens = set(_tokens(query_text))
        ranked: list[tuple[int, dict[str, Any]]] = []
        for record in self._records:
            destination_names = [record["destination"], *record.get("aliases", [])]
            destination_match = any(
                name.casefold() in query_text.casefold() for name in destination_names
            )
            searchable = json.dumps(record, ensure_ascii=False)
            overlap = len(query_tokens.intersection(_tokens(searchable)))
            score = overlap + (10 if destination_match else 0)
            if score:
                ranked.append((score, record))

        ranked.sort(key=lambda item: (-item[0], item[1]["destination"]))
        results = [
            {
                **record,
                "citation": f"[{record['source_id']}]",
            }
            for _, record in ranked[:limit]
        ]
        return {
            "query": query_text,
            "results": results,
            "source_ids": [record["source_id"] for record in results],
            "metadata": self.capability_metadata,
        }

    async def before_run(
        self,
        *,
        agent: Any,
        session: Any,
        context: Any,
        state: dict[str, Any],
    ) -> None:
        context.extend_instructions(
            self.source_id,
            (
                "Use retrieve_destination_context for destination, lodging-area, and activity "
                "guidance. Cite every retrieved claim with the returned [source_id]. Treat the "
                "records as curated workshop context, not live availability or booking data."
            ),
        )
        context.extend_tools(self.source_id, [self.retrieve_destination_context])


def _load_destination_records(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.is_file():
        raise FileNotFoundError(f"Destination grounding data not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid destination grounding JSON at {path}: {exc}") from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError("Destination grounding data must be a non-empty JSON array")

    records: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    for index, record in enumerate(payload):
        if not isinstance(record, dict):
            raise ValueError(f"Destination record {index} must be an object")
        source_id = record.get("source_id")
        destination = record.get("destination")
        if not isinstance(source_id, str) or not isinstance(destination, str):
            raise ValueError(
                f"Destination record {index} requires string source_id and destination"
            )
        if source_id in source_ids:
            raise ValueError(f"Duplicate destination source_id: {source_id}")
        source_ids.add(source_id)
        records.append(record)
    return tuple(records)


def _resolve_data_path(data_path: str | Path) -> Path:
    path = Path(data_path)
    if path.is_absolute() or path.is_file():
        return path
    repository_path = DEFAULT_DESTINATIONS_PATH.parents[1] / path
    return repository_path if repository_path.is_file() else path


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())
