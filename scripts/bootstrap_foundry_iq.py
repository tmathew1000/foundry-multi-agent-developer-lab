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
    storage_account: str
    storage_resource_id: str
    container: str
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
            "FOUNDRY_IQ_STORAGE_ACCOUNT_NAME": "storage_account",
            "FOUNDRY_IQ_STORAGE_RESOURCE_ID": "storage_resource_id",
            "FOUNDRY_IQ_KNOWLEDGE_CONTAINER": "container",
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
        _upload_documents(settings, credential)
        token = credential.get_token(SEARCH_SCOPE).token
        _put_search_object(
            settings,
            token,
            "knowledgesources",
            settings.knowledge_source,
            build_knowledge_source_payload(settings),
        )
        _wait_for_ingestion(settings, token)
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
    except (RuntimeError, ValueError) as exc:
        print(f"Foundry IQ bootstrap failed: {exc}", file=sys.stderr)
        return 1

    print(f"Foundry IQ ready: {settings.knowledge_base} with source {settings.knowledge_source}")
    return 0


def build_knowledge_source_payload(settings: BootstrapSettings) -> dict[str, Any]:
    model_parameters = {
        "resourceUri": settings.model_resource_uri,
        "deploymentId": settings.chat_deployment,
        "modelName": "gpt-5.4-mini",
    }
    embedding_parameters = {
        "resourceUri": settings.model_resource_uri,
        "deploymentId": settings.embedding_deployment,
        "modelName": "text-embedding-3-large",
    }
    return {
        "name": settings.knowledge_source,
        "kind": "azureBlob",
        "description": ("Curated TravelBuddy neighborhood, activity, and transit guidance."),
        "encryptionKey": None,
        "azureBlobParameters": {
            "connectionString": f"ResourceId={settings.storage_resource_id}",
            "containerName": settings.container,
            "folderPath": None,
            "isADLSGen2": False,
            "ingestionParameters": {
                "networkAccessMode": "public",
                "identity": None,
                "disableImageVerbalization": True,
                "chatCompletionModel": {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": model_parameters,
                },
                "embeddingModel": {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": embedding_parameters,
                },
                "contentExtractionMode": "minimal",
                "ingestionSchedule": None,
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
                "kind": "searchIndex",
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


def _upload_documents(settings: BootstrapSettings, credential: Any) -> None:
    try:
        from azure.core.exceptions import HttpResponseError
        from azure.storage.blob import BlobServiceClient, ContentSettings
    except ImportError as exc:
        raise RuntimeError("Install azure-storage-blob before provisioning Foundry IQ.") from exc
    documents = sorted(settings.documents_path.glob("*.md"))
    if not documents:
        raise RuntimeError(f"No Foundry IQ documents found in {settings.documents_path}.")

    service = BlobServiceClient(
        account_url=f"https://{settings.storage_account}.blob.core.windows.net",
        credential=credential,
    )
    container = service.get_container_client(settings.container)
    for document in documents:
        for attempt in range(1, 7):
            try:
                container.upload_blob(
                    name=document.name,
                    data=document.read_bytes(),
                    overwrite=True,
                    content_settings=ContentSettings(
                        content_type="text/markdown",
                        content_encoding="utf-8",
                    ),
                )
                break
            except HttpResponseError as exc:
                if exc.status_code not in {403, 404, 409, 429} or attempt == 6:
                    raise RuntimeError(f"Failed to upload {document.name}: {exc}") from exc
                time.sleep(10)
    print(f"Uploaded {len(documents)} Foundry IQ knowledge documents.")


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
    return _request_json("PUT", url, token, payload)


def _wait_for_ingestion(
    settings: BootstrapSettings,
    token: str,
    *,
    timeout_seconds: int = 600,
) -> None:
    url = (
        f"{settings.search_endpoint.rstrip('/')}/knowledgesources/"
        f"{quote(settings.knowledge_source, safe='')}/status"
        f"?api-version={quote(settings.api_version, safe='-')}"
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = _request_json("GET", url, token)
        status_text = json.dumps(status).casefold()
        if any(value in status_text for value in ('"status": "error"', '"status":"error"')):
            raise RuntimeError(f"Foundry IQ ingestion failed: {json.dumps(status)}")
        if any(
            value in status_text
            for value in (
                '"status": "success"',
                '"status":"success"',
                '"status": "completed"',
                '"status":"completed"',
            )
        ):
            print("Foundry IQ document ingestion completed.")
            return
        time.sleep(10)
    raise RuntimeError(f"Foundry IQ ingestion did not complete within {timeout_seconds} seconds.")


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
) -> Mapping[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    raw = ""
    for attempt in range(1, 7):
        try:
            with urlopen(request, timeout=90) as response:
                raw = response.read().decode("utf-8")
            break
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            retryable = exc.code in {403, 404, 409, 429, 500, 502, 503, 504}
            if not retryable or attempt == 6:
                raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
            time.sleep(10)
        except URLError as exc:
            if attempt == 6:
                raise RuntimeError(
                    f"{method} {url} could not reach Azure AI Search: {exc}"
                ) from exc
            time.sleep(10)
    try:
        result = json.loads(raw)
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
