from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from travel_buddy.config import TravelBuddySettings
from travel_buddy.foundry_iq import FoundryIQClient
from travel_buddy.preflight import parse_azd_env_values, post_provision_checks


def response_text(payload: Mapping[str, Any]) -> str:
    if payload.get("status") != "completed" or payload.get("error"):
        raise RuntimeError(f"Hosted response did not complete: {json.dumps(payload)}")
    output = payload.get("output")
    if not isinstance(output, list):
        raise RuntimeError("Hosted response output must be a JSON array.")
    text = "\n".join(
        part["text"]
        for item in output
        if isinstance(item, dict) and isinstance(item.get("content"), list)
        for part in item["content"]
        if isinstance(part, dict)
        and part.get("type") == "output_text"
        and isinstance(part.get("text"), str)
        and part["text"].strip()
    )
    if not text:
        raise RuntimeError("Hosted response completed without answer text.")
    return text


async def check_mcp(url: str) -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("destination_advisory", {"destination": "Tokyo"})
            if result.isError or not result.content:
                raise RuntimeError(f"MCP destination_advisory failed: {result}")


def main() -> int:
    print("Live smoke test: invokes MCP, Search, and the hosted agent; model charges may apply.")
    stage = "azd environment"
    try:
        completed = subprocess.run(
            ["azd", "env", "get-values"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        values = parse_azd_env_values(completed.stdout)
        blockers = [check for check in post_provision_checks(values) if check.blocking]
        if blockers:
            raise RuntimeError("; ".join(f"{c.name}: {c.detail}" for c in blockers))
        settings = TravelBuddySettings.from_env(values)
        settings.require_cloud()

        stage = "remote MCP"
        mcp_url = values.get("TRAVEL_BUDDY_MCP_URL") or (
            values["SERVICE_MCP_SERVER_URI"].rstrip("/") + "/mcp"
        )
        asyncio.run(asyncio.wait_for(check_mcp(mcp_url), timeout=90))
        print("PASS live MCP tool call")

        stage = "Foundry IQ"
        result = FoundryIQClient(
            endpoint=values["FOUNDRY_IQ_SEARCH_ENDPOINT"],
            knowledge_base=values["FOUNDRY_IQ_KNOWLEDGE_BASE"],
            knowledge_source=values["FOUNDRY_IQ_KNOWLEDGE_SOURCE"],
            api_version=values.get("FOUNDRY_IQ_API_VERSION", "2026-08-01-preview"),
        ).retrieve("Which Tokyo area has evening dining and convenient transit?")
        if not any(citation.get("type") == "file" for citation in result.citations):
            raise RuntimeError("Foundry IQ retrieval returned no file citations.")
        print(
            f"PASS live Foundry IQ retrieval ({len(result.answer)} answer characters, "
            f"{len(result.citations)} citations)"
        )

        stage = "hosted agent"
        from azure.identity import DefaultAzureCredential

        with DefaultAzureCredential() as credential:
            token = credential.get_token("https://ai.azure.com/.default").token
        endpoint = values.get("AGENT_TRAVEL_BUDDY_RESPONSES_ENDPOINT") or (
            f"{settings.project_endpoint.rstrip('/')}/agents/travel-buddy/endpoint/"
            "protocols/openai/responses?api-version=v1"
        )
        request = Request(
            endpoint,
            data=json.dumps(
                {
                    "input": (
                        "Plan three days in Tokyo from Seattle for two adults, 10-13 November "
                        "2026, hotel budget 200 USD per night, interested in food and history. "
                        "Use the available travel tools and return a consolidated itinerary."
                    ),
                    "stream": False,
                }
            ).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=240) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("Hosted response must be a JSON object.")
        answer = response_text(payload)
        print(f"PASS live hosted response ({len(answer)} answer characters)")
        print(f"Hosted response ID: {payload.get('id', '(not supplied)')}")
    except HTTPError as exc:
        print(
            f"FAIL live {stage}: HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}",
            file=sys.stderr,
        )
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"FAIL live {stage}: {exc.stderr}", file=sys.stderr)
        return 1
    except (
        OSError,
        URLError,
        RuntimeError,
        ValueError,
        KeyError,
        subprocess.TimeoutExpired,
        TimeoutError,
    ) as exc:
        print(f"FAIL live {stage}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
