from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SEARCH_SCOPE = "https://search.azure.com/.default"


@dataclass(frozen=True)
class BootstrapSettings:
    search_endpoint: str
    api_version: str
    knowledge_source: str
    knowledge_base: str
    model_resource_uri: str
    chat_deployment: str
    embedding_deployment: str
    documents_path: Path

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        repository_root: Path | None = None,
    ) -> BootstrapSettings:
        values = os.environ if env is None else env
        required = {
            "FOUNDRY_IQ_SEARCH_ENDPOINT": "search_endpoint",
            "FOUNDRY_IQ_API_VERSION": "api_version",
            "FOUNDRY_IQ_KNOWLEDGE_SOURCE": "knowledge_source",
            "FOUNDRY_IQ_KNOWLEDGE_BASE": "knowledge_base",
            "FOUNDRY_IQ_MODEL_RESOURCE_URI": "model_resource_uri",
            "FOUNDRY_IQ_CHAT_DEPLOYMENT_NAME": "chat_deployment",
            "FOUNDRY_IQ_EMBEDDING_DEPLOYMENT_NAME": "embedding_deployment",
        }
        missing = [name for name in required if not values.get(name, "").strip()]
        if missing:
            raise ValueError("Missing Foundry IQ deployment outputs: " + ", ".join(missing))
        root = repository_root or Path(__file__).resolve().parents[1]
        return cls(
            **{
                field_name: values[environment_name].strip()
                for environment_name, field_name in required.items()
            },
            documents_path=root / "data" / "foundry-iq",
        )


def main() -> int:
    try:
        settings = BootstrapSettings.from_env()
        credential = _default_credential()
        token = credential.get_token(SEARCH_SCOPE).token
        _put_search_object(
            settings,
            token,
            "knowledgesources",
            settings.knowledge_source,
            build_knowledge_source_payload(settings),
        )
        _upload_documents(settings, token)
        _put_search_object(
            settings,
            token,
            "knowledgebases",
            settings.knowledge_base,
            build_knowledge_base_payload(settings),
        )
        result = _retrieve(settings, token, smoke_test_payload(settings))
        if not _response_has_text(result):
            raise RuntimeError("Foundry IQ smoke test returned no answer text.")
        references = result.get("references")
        if not isinstance(references, list) or not any(
            isinstance(reference, dict) and reference.get("type") == "file"
            for reference in references
        ):
            raise RuntimeError("Foundry IQ smoke test returned no file citations.")
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Foundry IQ bootstrap failed: {exc}", file=sys.stderr)
        return 1

    print(f"Foundry IQ ready: {settings.knowledge_base} with source {settings.knowledge_source}")
    return 0


def build_knowledge_source_payload(settings: BootstrapSettings) -> dict[str, Any]:
    embedding_parameters = {
        "resourceUri": settings.model_resource_uri,
        "deploymentId": settings.embedding_deployment,
        "modelName": "text-embedding-3-large",
    }
    return {
        "name": settings.knowledge_source,
        "kind": "file",
        "description": ("Curated TravelBuddy neighborhood, activity, and transit guidance."),
        "encryptionKey": None,
        "fileParameters": {
            "ingestionParameters": {
                "embeddingModel": {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": embedding_parameters,
                },
                "contentExtractionMode": "minimal",
            },
        },
    }


def build_knowledge_base_payload(settings: BootstrapSettings) -> dict[str, Any]:
    return {
        "name": settings.knowledge_base,
        "description": (
            "Shared destination knowledge for the TravelBuddy Hotels and Activities agents."
        ),
        "retrievalInstructions": (
            "Use the travel destination source for neighborhood, lodging-area, transit, "
            "and activity guidance. Do not treat indicative workshop prices as live prices."
        ),
        "answerInstructions": (
            "Answer concisely from retrieved sources, preserve citations, and state when "
            "the knowledge does not include live availability or current wait times."
        ),
        "outputMode": "answerSynthesis",
        "knowledgeSources": [{"name": settings.knowledge_source}],
        "models": [
            {
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": settings.model_resource_uri,
                    "deploymentId": settings.chat_deployment,
                    "modelName": "gpt-5.4-mini",
                },
            }
        ],
        "encryptionKey": None,
        "retrievalReasoningEffort": {"kind": "auto"},
    }


def smoke_test_payload(settings: BootstrapSettings) -> dict[str, Any]:
    return {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Which Tokyo area fits a 200 EUR hotel budget, evening dining, "
                            "and convenient transit? Include a rainy-day activity."
                        ),
                    }
                ],
            }
        ],
        "knowledgeSourceParams": [
            {
                "knowledgeSourceName": settings.knowledge_source,
                "kind": "file",
                "includeReferences": True,
                "includeReferenceSourceData": True,
            }
        ],
        "includeActivity": True,
    }


def _default_credential() -> Any:
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError("Install project dependencies before provisioning Foundry IQ.") from exc
    return DefaultAzureCredential()


def _files_url(settings: BootstrapSettings) -> str:
    return (
        f"{settings.search_endpoint.rstrip('/')}/knowledgesources/"
        f"{quote(settings.knowledge_source, safe='')}/files"
        f"?api-version={quote(settings.api_version, safe='-')}"
    )


def _list_files(settings: BootstrapSettings, token: str) -> dict[str, str]:
    url = _files_url(settings)
    files: dict[str, str] = {}
    while url:
        page = _request_json("GET", url, token)
        entries = page.get("value")
        if not isinstance(entries, list):
            raise RuntimeError("Search file listing must contain a value array.")
        for entry in entries:
            if not isinstance(entry, dict):
                raise RuntimeError("Search file listing contains an invalid entry.")
            name, file_id = entry.get("fileName"), entry.get("fileId")
            if not isinstance(name, str) or not isinstance(file_id, str) or not file_id:
                raise RuntimeError("Search file listing is missing fileName or fileId.")
            if name in files:
                raise RuntimeError(
                    f"Duplicate Search file name {name}; resolve it before retrying."
                )
            files[name] = file_id
        next_url = page.get("@odata.nextLink")
        if next_url and (
            not isinstance(next_url, str)
            or not next_url.startswith(settings.search_endpoint.rstrip("/") + "/")
        ):
            raise RuntimeError("Search returned an unexpected file continuation URL.")
        url = next_url or ""
    return files


def _upload_documents(settings: BootstrapSettings, token: str) -> None:
    documents = sorted(settings.documents_path.glob("*.md"))
    if not documents:
        raise RuntimeError(f"No Foundry IQ documents found in {settings.documents_path}.")
    files = _list_files(settings, token)
    for document in documents:
        data = document.read_bytes()
        file_id = files.get(document.name)
        if file_id:
            boundary = "travelbuddy-file-boundary"
            data = (
                (
                    f"--{boundary}\r\n"
                    'Content-Disposition: form-data; name="content"; '
                    f'filename="{document.name}"\r\n'
                    "Content-Type: application/octet-stream\r\n\r\n"
                ).encode()
                + data
                + f"\r\n--{boundary}--\r\n".encode()
            )
            url = (
                f"{settings.search_endpoint.rstrip('/')}/knowledgesources"
                f"('{quote(settings.knowledge_source, safe='')}')/files"
                f"('{quote(file_id, safe='')}')?api-version={settings.api_version}"
            )
            result = _request_json(
                "PUT",
                url,
                token,
                raw_data=data,
                content_type=f"multipart/form-data; boundary={boundary}",
                timeout_seconds=240,
            )
        else:
            result = _request_json(
                "POST",
                _files_url(settings),
                token,
                raw_data=data,
                content_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{document.name}"'},
                timeout_seconds=240,
            )
        if not isinstance(result.get("fileId"), str) or not result["fileId"]:
            raise RuntimeError(f"Search did not confirm file processing for {document.name}.")
        print(f"Processed Foundry IQ file: {document.name}")
    print(f"Uploaded and indexed {len(documents)} Foundry IQ knowledge documents.")


def _put_search_object(
    settings: BootstrapSettings,
    token: str,
    collection: str,
    name: str,
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    url = (
        f"{settings.search_endpoint.rstrip('/')}/{collection}/{quote(name, safe='')}"
        f"?api-version={quote(settings.api_version, safe='-')}"
    )
    return _request_json("PUT", url, token, payload, allow_empty=True)


def _retrieve(
    settings: BootstrapSettings,
    token: str,
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    url = (
        f"{settings.search_endpoint.rstrip('/')}/knowledgebases/"
        f"{quote(settings.knowledge_base, safe='')}/retrieve"
        f"?api-version={quote(settings.api_version, safe='-')}"
    )
    return _request_json("POST", url, token, payload)


def _request_json(
    method: str,
    url: str,
    token: str,
    payload: Mapping[str, Any] | None = None,
    *,
    allow_empty: bool = False,
    raw_data: bytes | None = None,
    content_type: str = "application/json",
    headers: Mapping[str, str] | None = None,
    timeout_seconds: int = 90,
) -> Mapping[str, Any]:
    data = (
        raw_data
        if raw_data is not None
        else (None if payload is None else json.dumps(payload).encode("utf-8"))
    )
    request = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
            **(headers or {}),
        },
        method=method,
    )
    raw = ""
    can_retry = method != "POST" or raw_data is None
    for attempt in range(1, 7):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
            break
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            retryable = can_retry and exc.code in {403, 404, 409, 429, 500, 502, 503, 504}
            if not retryable or attempt == 6:
                raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
            time.sleep(10)
        except URLError as exc:
            if not can_retry or attempt == 6:
                raise RuntimeError(
                    f"{method} {url} could not reach Azure AI Search: {exc}"
                ) from exc
            time.sleep(10)
    try:
        result = {} if allow_empty and not raw.strip() else json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {url} returned invalid JSON.") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{method} {url} returned a non-object JSON response.")
    return result


def _response_has_text(payload: Mapping[str, Any]) -> bool:
    response = payload.get("response", [])
    if not isinstance(response, list):
        return False
    return any(
        isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip()
        for item in response
        if isinstance(item, dict)
        for part in item.get("content", [])
        if isinstance(item.get("content"), list)
    )


if __name__ == "__main__":
    raise SystemExit(main())
