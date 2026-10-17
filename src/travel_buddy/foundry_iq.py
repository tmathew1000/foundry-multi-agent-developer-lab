from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from agent_framework import ContextProvider

SEARCH_SCOPE = "https://search.azure.com/.default"


class TokenCredential(Protocol):
    def get_token(self, *scopes: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class FoundryIQResult:
    answer: str
    citations: tuple[dict[str, Any], ...]
    activity: tuple[dict[str, Any], ...]


class FoundryIQClient:
    def __init__(
        self,
        *,
        endpoint: str,
        knowledge_base: str,
        knowledge_source: str,
        api_version: str,
        credential: TokenCredential | None = None,
        sender: Callable[[Request, float], Mapping[str, Any]] | None = None,
        timeout_seconds: float = 60,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.knowledge_base = knowledge_base
        self.knowledge_source = knowledge_source
        self.api_version = api_version
        self.credential = credential or _default_credential()
        self.sender = sender or _send_json
        self.timeout_seconds = timeout_seconds

    def retrieve(self, query: str) -> FoundryIQResult:
        query_text = query.strip()
        if not query_text:
            raise ValueError("query cannot be empty")

        token = self.credential.get_token(SEARCH_SCOPE).token
        url = (
            f"{self.endpoint}/knowledgebases/{quote(self.knowledge_base, safe='')}"
            f"/retrieve?api-version={quote(self.api_version, safe='-')}"
        )
        payload = {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Answer only from the TravelBuddy destination knowledge. "
                                "Preserve source citations and say when the knowledge base "
                                "does not contain current or live information."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": query_text}],
                },
            ],
            "knowledgeSourceParams": [
                {
                    "knowledgeSourceName": self.knowledge_source,
                    "kind": "searchIndex",
                    "includeReferences": True,
                    "includeReferenceSourceData": True,
                }
            ],
            "includeActivity": True,
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        response = self.sender(request, self.timeout_seconds)
        return _parse_retrieval_response(response)


class FoundryIQGroundingProvider(ContextProvider):
    capability_metadata = {
        "kind": "foundry_iq_knowledge_base",
        "citation_format": "retrieval references",
        "limitations": (
            "Curated workshop knowledge; it is not live availability, booking data, "
            "exchange rates, or attraction wait times."
        ),
    }

    def __init__(
        self,
        *,
        endpoint: str,
        knowledge_base: str,
        knowledge_source: str,
        api_version: str = "2026-08-01-preview",
        client: FoundryIQClient | None = None,
    ) -> None:
        super().__init__(source_id="travel_buddy.foundry_iq")
        self.client = client or FoundryIQClient(
            endpoint=endpoint,
            knowledge_base=knowledge_base,
            knowledge_source=knowledge_source,
            api_version=api_version,
        )

    def retrieve_destination_knowledge(
        self,
        query: Annotated[
            str,
            "Destination, neighborhood, transit, lodging-area, or activity question",
        ],
    ) -> dict[str, object]:
        result = self.client.retrieve(query)
        return {
            "query": query.strip(),
            "answer": result.answer,
            "citations": list(result.citations),
            "activity": list(result.activity),
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
                "Use retrieve_destination_knowledge for destination, lodging-area, transit, "
                "and activity guidance. Preserve the returned citations in the answer. Treat "
                "the knowledge as curated planning guidance, not live availability or booking "
                "data. State when the knowledge base does not support a requested live fact."
            ),
        )
        context.extend_tools(
            self.source_id,
            [self.retrieve_destination_knowledge],
        )


def _default_credential() -> TokenCredential:
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError("Install azure-identity before enabling Foundry IQ grounding.") from exc
    return DefaultAzureCredential()


def _send_json(request: Request, timeout_seconds: float) -> Mapping[str, Any]:
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Foundry IQ retrieval failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Foundry IQ retrieval could not reach Azure AI Search: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Foundry IQ retrieval returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Foundry IQ retrieval response must be a JSON object.")
    return payload


def _parse_retrieval_response(payload: Mapping[str, Any]) -> FoundryIQResult:
    texts: list[str] = []
    citations: list[dict[str, Any]] = []
    response_items = payload.get("response", [])
    if isinstance(response_items, list):
        for item in response_items:
            if not isinstance(item, dict):
                continue
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
                references = part.get("references", [])
                if isinstance(references, list):
                    citations.extend(
                        reference for reference in references if isinstance(reference, dict)
                    )
    if not texts:
        raise RuntimeError("Foundry IQ retrieval returned no answer text.")

    activity_value = payload.get("activity", [])
    activity = (
        tuple(item for item in activity_value if isinstance(item, dict))
        if isinstance(activity_value, list)
        else ()
    )
    return FoundryIQResult(
        answer="\n".join(texts),
        citations=tuple(citations),
        activity=activity,
    )
