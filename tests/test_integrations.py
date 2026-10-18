import unittest

from travel_buddy.config import TravelBuddySettings
from travel_buddy.foundry_iq import FoundryIQGroundingProvider
from travel_buddy.grounding import DestinationGroundingProvider
from travel_buddy.integrations import build_grounding_provider


class IntegrationFactoryTests(unittest.TestCase):
    def test_builds_local_provider_by_default(self) -> None:
        provider = build_grounding_provider(
            TravelBuddySettings.from_env({}),
            factory=None,
        )

        self.assertIsInstance(provider, DestinationGroundingProvider)

    def test_builds_foundry_iq_provider_when_selected(self) -> None:
        settings = TravelBuddySettings.from_env(
            {
                "TRAVEL_BUDDY_GROUNDING_PROVIDER": "foundry_iq",
                "FOUNDRY_IQ_SEARCH_ENDPOINT": "https://search.example.test",
                "FOUNDRY_IQ_KNOWLEDGE_BASE": "travel-destinations",
                "FOUNDRY_IQ_KNOWLEDGE_SOURCE": "travel-destinations-files",
            }
        )

        provider = build_grounding_provider(settings, factory=None)

        self.assertIsInstance(provider, FoundryIQGroundingProvider)
