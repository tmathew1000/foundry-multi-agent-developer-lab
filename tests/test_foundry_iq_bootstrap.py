import importlib.util
import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
