import importlib.util
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

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
            knowledge_source="travel-destinations-files",
            knowledge_base="travel-destinations",
            model_resource_uri="https://foundry.services.ai.azure.com",
            chat_deployment="travel-model",
            embedding_deployment="travel-embeddings",
            documents_path=Path("data/foundry-iq"),
        )

    def test_settings_do_not_require_storage_outputs(self) -> None:
        settings = bootstrap.BootstrapSettings.from_env(
            {
                "FOUNDRY_IQ_SEARCH_ENDPOINT": "https://search.example.test",
                "FOUNDRY_IQ_API_VERSION": "2026-08-01-preview",
                "FOUNDRY_IQ_KNOWLEDGE_SOURCE": "travel-destinations-files",
                "FOUNDRY_IQ_KNOWLEDGE_BASE": "travel-destinations",
                "FOUNDRY_IQ_MODEL_RESOURCE_URI": "https://foundry.services.ai.azure.com",
                "FOUNDRY_IQ_CHAT_DEPLOYMENT_NAME": "travel-model",
                "FOUNDRY_IQ_EMBEDDING_DEPLOYMENT_NAME": "travel-embeddings",
            }
        )
        self.assertEqual("travel-destinations-files", settings.knowledge_source)

    def test_upload_failure_does_not_repoint_knowledge_base(self) -> None:
        with (
            patch.object(bootstrap.BootstrapSettings, "from_env", return_value=self.settings()),
            patch.object(bootstrap, "_default_credential"),
            patch.object(bootstrap, "_put_search_object") as put,
            patch.object(bootstrap, "_upload_documents", side_effect=RuntimeError("upload failed")),
        ):
            self.assertEqual(1, bootstrap.main())
        put.assert_called_once()
        self.assertEqual("knowledgesources", put.call_args.args[2])

    def test_bootstrap_requires_file_citations_as_well_as_text(self) -> None:
        text = {"response": [{"content": [{"type": "text", "text": "Tokyo guidance"}]}]}
        for references, expected in (
            ([], 1),
            ([{"type": "azureBlob", "id": "0"}], 1),
            ([{"type": "file", "id": "0"}], 0),
        ):
            with (
                self.subTest(references=references),
                patch.object(bootstrap.BootstrapSettings, "from_env", return_value=self.settings()),
                patch.object(bootstrap, "_default_credential"),
                patch.object(bootstrap, "_put_search_object"),
                patch.object(bootstrap, "_upload_documents"),
                patch.object(
                    bootstrap, "_retrieve", return_value={**text, "references": references}
                ),
            ):
                self.assertEqual(expected, bootstrap.main())

    def test_knowledge_source_uses_direct_files_and_minimal_extraction(self) -> None:
        payload = bootstrap.build_knowledge_source_payload(self.settings())
        parameters = payload["fileParameters"]

        self.assertEqual("file", payload["kind"])
        self.assertEqual("minimal", parameters["ingestionParameters"]["contentExtractionMode"])
        self.assertNotIn("connectionString", parameters)
        self.assertNotIn("networkAccessMode", parameters["ingestionParameters"])
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
            [{"name": "travel-destinations-files"}],
            payload["knowledgeSources"],
        )

    def test_smoke_test_matches_file_source(self) -> None:
        self.assertEqual(
            "file",
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

    def test_list_files_follows_pagination(self) -> None:
        next_url = "https://search.example.test/next?page=2"
        with (
            patch.object(
                bootstrap,
                "_request_json",
                side_effect=[
                    {
                        "value": [{"fileName": "a.md", "fileId": "file-a"}],
                        "@odata.nextLink": next_url,
                    },
                    {"value": [{"fileName": "b.md", "fileId": "file-b"}]},
                ],
            ) as request,
        ):
            self.assertEqual(
                {"a.md": "file-a", "b.md": "file-b"},
                bootstrap._list_files(self.settings(), "token"),
            )
        self.assertEqual(next_url, request.call_args.args[1])

    def test_invalid_file_list_is_rejected(self) -> None:
        for page in (
            {},
            {"value": ["bad"]},
            {"value": [{"fileName": "a.md"}]},
            {
                "value": [
                    {"fileName": "a.md", "fileId": "one"},
                    {"fileName": "a.md", "fileId": "two"},
                ]
            },
            {"value": [], "@odata.nextLink": "https://untrusted.example/files"},
        ):
            with (
                self.subTest(page=page),
                patch.object(bootstrap, "_request_json", return_value=page),
                self.assertRaises(RuntimeError),
            ):
                bootstrap._list_files(self.settings(), "token")

    def test_upload_new_file_and_update_existing_file(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.md").write_text("new guidance", encoding="utf-8")
            (root / "b.md").write_text("updated guidance", encoding="utf-8")
            settings = replace(self.settings(), documents_path=root)
            with patch.object(
                bootstrap,
                "_request_json",
                side_effect=[
                    {"value": [{"fileName": "b.md", "fileId": "file-b"}]},
                    {"fileId": "file-a"},
                    {"fileId": "file-b"},
                ],
            ) as request:
                bootstrap._upload_documents(settings, "token")
            upload, update = request.call_args_list[1:]
            self.assertEqual("POST", upload.args[0])
            self.assertEqual(b"new guidance", upload.kwargs["raw_data"])
            self.assertIn('filename="a.md"', upload.kwargs["headers"]["Content-Disposition"])
            self.assertEqual("PUT", update.args[0])
            self.assertIn("/files('file-b')?", update.args[1])
            self.assertIn(b' name="content"; filename="b.md"', update.kwargs["raw_data"])
            self.assertIn(b"updated guidance", update.kwargs["raw_data"])
            self.assertTrue(update.kwargs["content_type"].startswith("multipart/form-data"))
            self.assertEqual(240, update.kwargs["timeout_seconds"])

    def test_empty_document_directory_is_an_error(self) -> None:
        with TemporaryDirectory() as directory, self.assertRaisesRegex(RuntimeError, "No Foundry"):
            bootstrap._upload_documents(
                replace(self.settings(), documents_path=Path(directory)), "token"
            )

    def test_upload_requires_processing_confirmation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.md").write_text("content", encoding="utf-8")
            with (
                patch.object(bootstrap, "_request_json", side_effect=[{"value": []}, {}]),
                self.assertRaisesRegex(RuntimeError, "did not confirm"),
            ):
                bootstrap._upload_documents(replace(self.settings(), documents_path=root), "token")

    def test_post_is_not_retried_after_uncertain_failure(self) -> None:
        for failure in (
            HTTPError("https://example.test", 503, "unavailable", None, None),
            URLError("lost connection"),
        ):
            with (
                self.subTest(failure=failure),
                patch.object(bootstrap, "urlopen", side_effect=failure) as request,
                self.assertRaises(RuntimeError),
            ):
                bootstrap._request_json("POST", "https://example.test", "token", raw_data=b"file")
            request.assert_called_once()

    def test_binary_upload_uses_auth_headers_and_processing_timeout(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"fileId": "id"}).encode()
        with patch.object(bootstrap, "urlopen", return_value=response) as request:
            bootstrap._request_json(
                "POST",
                "https://example.test",
                "token",
                raw_data=b"file",
                content_type="application/octet-stream",
                timeout_seconds=240,
                headers={"Content-Disposition": 'attachment; filename="a.md"'},
            )
        self.assertEqual(b"file", request.call_args.args[0].data)
        self.assertEqual(240, request.call_args.kwargs["timeout"])


if __name__ == "__main__":
    unittest.main()
