import asyncio
import unittest

from travel_buddy.grounding import DestinationGroundingProvider


class FakeContext:
    def __init__(self) -> None:
        self.instructions = []
        self.tools = []

    def extend_instructions(self, source_id, instructions) -> None:
        self.instructions.append((source_id, instructions))

    def extend_tools(self, source_id, tools) -> None:
        self.tools.append((source_id, tools))


class DestinationGroundingTests(unittest.TestCase):
    def test_retrieval_returns_relevant_record_and_source_id(self) -> None:
        provider = DestinationGroundingProvider()

        result = provider.retrieve_destination_context("Tokyo hotel area with evening dining")

        self.assertEqual("destination:tokyo", result["source_ids"][0])
        self.assertEqual("Tokyo", result["results"][0]["destination"])
        self.assertEqual("[destination:tokyo]", result["results"][0]["citation"])
        self.assertIn(
            "extensive evening dining",
            result["results"][0]["hotel_areas"][0],
        )

    def test_retrieval_ranks_a_second_destination_with_its_source_id(self) -> None:
        provider = DestinationGroundingProvider()

        result = provider.retrieve_destination_context(
            "Lisbon historic neighborhoods and public transit", limit=1
        )

        self.assertEqual(["destination:lisbon"], result["source_ids"])
        self.assertEqual("Lisbon", result["results"][0]["destination"])

    def test_context_provider_injects_cited_retrieval_capability(self) -> None:
        provider = DestinationGroundingProvider()
        context = FakeContext()

        asyncio.run(
            provider.before_run(
                agent=object(),
                session=object(),
                context=context,
                state={},
            )
        )

        self.assertEqual(provider.source_id, context.instructions[0][0])
        self.assertIn("[source_id]", context.instructions[0][1])
        self.assertEqual(
            "retrieve_destination_context",
            context.tools[0][1][0].__name__,
        )


if __name__ == "__main__":
    unittest.main()
