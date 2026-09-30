import unittest

from travel_buddy.config import (
    ConfigurationError,
    TravelBuddySettings,
    resolve_model_deployment,
)


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

    def test_model_deployment_resolves_from_azd_metadata(self) -> None:
        settings = TravelBuddySettings.from_env(
            {
                "AI_PROJECT_DEPLOYMENTS": (
                    '[{"name":"travel-model","model":{"name":"gpt-5.4-mini"}}]'
                )
            }
        )

        self.assertEqual("travel-model", settings.model_deployment)

    def test_model_deployment_resolves_from_escaped_azd_output(self) -> None:
        settings = TravelBuddySettings.from_env(
            {"AI_PROJECT_DEPLOYMENTS": '[{\\"name\\":\\"travel-model\\"}]'}
        )

        self.assertEqual("travel-model", settings.model_deployment)

    def test_explicit_model_deployment_takes_precedence(self) -> None:
        name = resolve_model_deployment(
            {
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": "candidate-model",
                "AI_PROJECT_DEPLOYMENTS": '[{"name":"travel-model"}]',
            }
        )

        self.assertEqual("candidate-model", name)

    def test_multiple_model_deployments_require_explicit_selection(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "multiple deployments"):
            resolve_model_deployment(
                {"AI_PROJECT_DEPLOYMENTS": '[{"name":"one"},{"name":"two"}]'}
            )


if __name__ == "__main__":
    unittest.main()
