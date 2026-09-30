import unittest

from travel_buddy.config import ConfigurationError, TravelBuddySettings


class TravelBuddySettingsTests(unittest.TestCase):
    def test_offline_settings_do_not_require_credentials_until_cloud_build(self) -> None:
        settings = TravelBuddySettings.from_env({})

        with self.assertRaisesRegex(ConfigurationError, "FOUNDRY_PROJECT_ENDPOINT"):
            settings.require_cloud()

    def test_destination_grounding_path_can_be_configured(self) -> None:
        settings = TravelBuddySettings.from_env(
            {"TRAVEL_BUDDY_DESTINATIONS_PATH": "fixtures/destinations.json"}
        )

        self.assertEqual("fixtures/destinations.json", settings.grounding.data_path)


if __name__ == "__main__":
    unittest.main()
