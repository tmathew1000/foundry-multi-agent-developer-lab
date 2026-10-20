import unittest

from travel_buddy.config import (
    ConfigurationError,
    TravelBuddySettings,
    resolve_mcp_url,
    resolve_model_deployment,
)
from travel_buddy.preflight import parse_azd_env_values


class TravelBuddySettingsTests(unittest.TestCase):
    def test_mcp_deployment_alias_is_normalized(self) -> None:
        for uri in ("https://example.test", "https://example.test/", "https://example.test/mcp/"):
            with self.subTest(uri=uri):
                settings = TravelBuddySettings.from_env({"SERVICE_MCP_SERVER_URI": uri})
                self.assertEqual("https://example.test/mcp", settings.mcp_url)

    def test_explicit_mcp_url_takes_precedence(self) -> None:
        self.assertEqual(
            "https://custom.test/tools",
            resolve_mcp_url(
                {
                    "TRAVEL_BUDDY_MCP_URL": " https://custom.test/tools ",
                    "SERVICE_MCP_SERVER_URI": "https://example.test",
                }
            ),
        )
        self.assertIsNone(resolve_mcp_url({}))

    def test_provisioned_knowledge_does_not_implicitly_enable_foundry_iq(self) -> None:
        values = {
            "FOUNDRY_IQ_SEARCH_ENDPOINT": "https://search.example.test",
            "FOUNDRY_IQ_KNOWLEDGE_BASE": "travel-destinations",
            "FOUNDRY_IQ_KNOWLEDGE_SOURCE": "travel-destinations-files",
        }
        self.assertEqual("local", TravelBuddySettings.from_env(values).grounding.provider)
        values["TRAVEL_BUDDY_GROUNDING_PROVIDER"] = "foundry_iq"
        self.assertEqual("foundry_iq", TravelBuddySettings.from_env(values).grounding.provider)

    def test_provider_selection_survives_import_of_exported_azd_values(self) -> None:
        values = parse_azd_env_values(
            'TRAVEL_BUDDY_GROUNDING_PROVIDER="foundry_iq"\n'
            'FOUNDRY_IQ_SEARCH_ENDPOINT="https://search.example.test"\n'
            'FOUNDRY_IQ_KNOWLEDGE_BASE="travel-destinations"\n'
            'FOUNDRY_IQ_KNOWLEDGE_SOURCE="travel-destinations-files"\n'
            'SERVICE_MCP_SERVER_URI="https://mcp.example.test/"\n'
        )
        settings = TravelBuddySettings.from_env(values)
        self.assertEqual("foundry_iq", settings.grounding.provider)
        self.assertEqual("https://mcp.example.test/mcp", settings.mcp_url)

    def test_project_endpoint_aliases_match_preflight(self) -> None:
        for name in ("AZURE_AI_PROJECT_ENDPOINT", "AZURE_AIPROJECT_ENDPOINT"):
            with self.subTest(name=name):
                settings = TravelBuddySettings.from_env(
                    {name: "https://example.test/api/projects/lab"}
                )
                self.assertEqual("https://example.test/api/projects/lab", settings.project_endpoint)

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
            resolve_model_deployment({"AI_PROJECT_DEPLOYMENTS": '[{"name":"one"},{"name":"two"}]'})

    def test_foundry_iq_grounding_requires_all_remote_values(self) -> None:
        with self.assertRaisesRegex(
            ConfigurationError,
            "FOUNDRY_IQ_KNOWLEDGE_BASE",
        ):
            TravelBuddySettings.from_env(
                {
                    "TRAVEL_BUDDY_GROUNDING_PROVIDER": "foundry_iq",
                    "FOUNDRY_IQ_SEARCH_ENDPOINT": "https://search.example.test",
                }
            )

    def test_foundry_iq_grounding_reads_remote_values(self) -> None:
        settings = TravelBuddySettings.from_env(
            {
                "TRAVEL_BUDDY_GROUNDING_PROVIDER": "foundry_iq",
                "FOUNDRY_IQ_SEARCH_ENDPOINT": "https://search.example.test",
                "FOUNDRY_IQ_KNOWLEDGE_BASE": "travel-destinations",
                "FOUNDRY_IQ_KNOWLEDGE_SOURCE": "travel-destinations-files",
            }
        )

        self.assertEqual("foundry_iq", settings.grounding.provider)
        self.assertEqual(
            "travel-destinations",
            settings.grounding.knowledge_base,
        )


if __name__ == "__main__":
    unittest.main()
