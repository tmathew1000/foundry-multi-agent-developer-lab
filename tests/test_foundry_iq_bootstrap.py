import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "bootstrap_foundry_iq.py"
SPEC = importlib.util.spec_from_file_location("bootstrap_foundry_iq", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bootstrap
SPEC.loader.exec_module(bootstrap)


class FoundryIQBootstrapTests(unittest.TestCase):
    def settings(self):
        return bootstrap.BootstrapSettings(
            search_endpoint="https://search.example.test",
            api_version="2026-08-01-preview",
            knowledge_source="travel-destinations-blob",
            knowledge_base="travel-destinations",
            storage_account="sttravel",
            storage_resource_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/sttravel",
            container="travel-knowledge",
            model_resource_uri="https://foundry.services.ai.azure.com",
            chat_deployment="travel-model",
            embedding_deployment="travel-embeddings",
            documents_path=Path("data/foundry-iq"),
        )

    def test_knowledge_source_uses_resource_id_and_managed_identity(self) -> None:
        payload = bootstrap.build_knowledge_source_payload(self.settings())
        parameters = payload["azureBlobParameters"]

        self.assertTrue(parameters["connectionString"].startswith("ResourceId="))
        self.assertIsNone(parameters["ingestionParameters"]["identity"])
        self.assertTrue(parameters["ingestionParameters"]["disableImageVerbalization"])
        self.assertNotIn("chatCompletionModel", parameters["ingestionParameters"])
        self.assertEqual(
            "travel-embeddings",
            parameters["ingestionParameters"]["embeddingModel"]["azureOpenAIParameters"][
                "deploymentId"
            ],
        )

    def test_knowledge_base_enables_answer_synthesis(self) -> None:
        payload = bootstrap.build_knowledge_base_payload(self.settings())

        self.assertEqual("answerSynthesis", payload["outputMode"])
        self.assertEqual(
            [{"name": "travel-destinations-blob"}],
            payload["knowledgeSources"],
        )

    def test_smoke_test_matches_blob_source(self) -> None:
        self.assertEqual(
            "azureBlob",
            bootstrap.smoke_test_payload(self.settings())["knowledgeSourceParams"][0]["kind"],
        )

    def test_empty_body_is_allowed_only_for_put_operations(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"  "
        with patch.object(bootstrap, "urlopen", return_value=response):
            self.assertEqual(
                {},
                bootstrap._put_search_object(
                    self.settings(), "token", "knowledgesources", "source", {}
                ),
            )
            with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
                bootstrap._request_json("GET", "https://example.test", "token")

    def test_nonempty_invalid_json_is_never_accepted(self) -> None:
        response = MagicMock()
        with patch.object(bootstrap, "urlopen", return_value=response):
            for raw in (b"broken", b"[]"):
                response.__enter__.return_value.read.return_value = raw
                with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                    bootstrap._request_json(
                        "PUT", "https://example.test", "token", {}, allow_empty=True
                    )

    def test_ingestion_waits_for_current_sync_then_completes(self) -> None:
        last = {"endTime": "2026-10-18T12:00:00Z", "itemsUpdatesFailed": 0}
        statuses = [
            {"lastSynchronizationState": last, "currentSynchronizationState": {"startTime": "now"}},
            {"lastSynchronizationState": last, "currentSynchronizationState": None},
        ]
        with (
            patch.object(bootstrap, "_request_json", side_effect=statuses) as request,
            patch.object(bootstrap.time, "sleep"),
        ):
            bootstrap._wait_for_ingestion(self.settings(), "token")
        self.assertEqual(2, request.call_count)

    def test_ingestion_rejects_failures_even_when_finished(self) -> None:
        for failure in ({"itemsUpdatesFailed": 1}, {"errors": ["bad document"]}):
            status = {
                "lastSynchronizationState": {"endTime": "now", **failure},
                "currentSynchronizationState": None,
            }
            with (
                self.subTest(failure=failure),
                patch.object(bootstrap, "_request_json", return_value=status),
                self.assertRaisesRegex(RuntimeError, "ingestion failed"),
            ):
                bootstrap._wait_for_ingestion(self.settings(), "token")

    def test_ingestion_does_not_treat_nested_success_as_completed(self) -> None:
        with (
            patch.object(bootstrap, "_request_json", return_value={"step": {"status": "success"}}),
            patch.object(bootstrap.time, "monotonic", side_effect=[0, 0, 601]),
            patch.object(bootstrap.time, "sleep"),
            self.assertRaisesRegex(RuntimeError, "did not complete"),
        ):
            bootstrap._wait_for_ingestion(self.settings(), "token")

    def test_storage_policy_failure_has_actionable_error(self) -> None:
        completed = MagicMock(returncode=0, stdout='{"access":"Disabled"}')
        with (
            patch.object(bootstrap.subprocess, "run", return_value=completed),
            self.assertRaisesRegex(RuntimeError, "IP allowlist"),
        ):
            bootstrap._check_storage_network(self.settings())

    def test_storage_network_accepts_enabled_public_endpoint(self) -> None:
        completed = MagicMock(returncode=0, stdout='{"access":"Enabled"}')
        with patch.object(bootstrap.subprocess, "run", return_value=completed):
            bootstrap._check_storage_network(self.settings())


if __name__ == "__main__":
    unittest.main()
