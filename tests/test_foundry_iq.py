import asyncio
import json
import unittest

from travel_buddy.foundry_iq import (
    FoundryIQClient,
    FoundryIQGroundingProvider,
)


class FakeToken:
    token = "test-token"


class FakeCredential:
    def get_token(self, *scopes, **kwargs):
        self.scopes = scopes
        return FakeToken()


class FakeContext:
    def __init__(self) -> None:
        self.instructions = []
        self.tools = []

    def extend_instructions(self, source_id, instructions) -> None:
        self.instructions.append((source_id, instructions))

    def extend_tools(self, source_id, tools) -> None:
        self.tools.append((source_id, tools))


class FoundryIQTests(unittest.TestCase):
    def test_client_builds_authenticated_retrieval_and_preserves_citations(self) -> None:
        captured = {}

        def send(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data)
            captured["timeout"] = timeout
            return {
                "response": [
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": "Shinjuku fits the request [1].",
                                "references": [
                                    {
                                        "id": "1",
                                        "sourceName": "travel-destinations-blob",
                                    }
                                ],
                            }
                        ]
                    }
                ],
                "activity": [{"type": "modelQueryPlanning"}],
            }

        client = FoundryIQClient(
            endpoint="https://search.example.test",
            knowledge_base="travel destinations",
            knowledge_source="travel-destinations-blob",
            api_version="2026-08-01-preview",
            credential=FakeCredential(),
            sender=send,
        )

        result = client.retrieve("Tokyo evening dining and rainy-day activity")

        self.assertIn("travel%20destinations/retrieve", captured["url"])
        self.assertEqual("Bearer test-token", captured["headers"]["Authorization"])
        self.assertTrue(captured["payload"]["includeActivity"])
        self.assertEqual("azureBlob", captured["payload"]["knowledgeSourceParams"][0]["kind"])
        self.assertEqual("Shinjuku fits the request [1].", result.answer)
        self.assertEqual("1", result.citations[0]["id"])
        self.assertEqual("modelQueryPlanning", result.activity[0]["type"])

    def test_client_rejects_response_without_answer_text(self) -> None:
        client = FoundryIQClient(
            endpoint="https://search.example.test",
            knowledge_base="travel-destinations",
            knowledge_source="travel-destinations-blob",
            api_version="2026-08-01-preview",
            credential=FakeCredential(),
            sender=lambda request, timeout: {"response": []},
        )

        with self.assertRaisesRegex(RuntimeError, "no answer text"):
            client.retrieve("Tokyo")

    def test_context_provider_exposes_foundry_iq_retrieval(self) -> None:
        class FakeClient:
            def retrieve(self, query):
                return type(
                    "Result",
                    (),
                    {
                        "answer": "Use Shinjuku [1].",
                        "citations": ({"id": "1"},),
                        "activity": (),
                    },
                )()

        provider = FoundryIQGroundingProvider(
            endpoint="https://search.example.test",
            knowledge_base="travel-destinations",
            knowledge_source="travel-destinations-blob",
            client=FakeClient(),
        )
        context = FakeContext()

        asyncio.run(
            provider.before_run(
                agent=object(),
                session=object(),
                context=context,
                state={},
            )
        )
        result = provider.retrieve_destination_knowledge("Tokyo")

        self.assertIn("Preserve the returned citations", context.instructions[0][1])
        self.assertEqual(
            "retrieve_destination_knowledge",
            context.tools[0][1][0].__name__,
        )
        self.assertEqual("Use Shinjuku [1].", result["answer"])
        self.assertEqual([{"id": "1"}], result["citations"])
