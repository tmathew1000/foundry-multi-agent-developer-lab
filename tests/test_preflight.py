import unittest

from travel_buddy.preflight import (
    merge_environment_values,
    parse_azd_env_values,
    parse_azure_account,
    post_provision_checks,
)


class PreflightTests(unittest.TestCase):
    def test_parse_enabled_azure_account(self) -> None:
        account = parse_azure_account(
            """
            {
              "id": "sub-123",
              "name": "Developer Subscription",
              "state": "Enabled",
              "tenantId": "tenant-456"
            }
            """
        )

        self.assertEqual("sub-123", account.subscription_id)
        self.assertEqual("Enabled", account.state)

    def test_parse_azd_environment_values(self) -> None:
        values = parse_azd_env_values(
            'AZURE_AI_PROJECT_ENDPOINT="https://example.test/projects/lab"\n'
            'AZURE_AI_MODEL_DEPLOYMENT_NAME="travel-model"\n'
            "TRAVEL_BUDDY_MCP_URL='https://mcp.example.test/mcp'\n"
        )

        self.assertEqual("travel-model", values["AZURE_AI_MODEL_DEPLOYMENT_NAME"])
        self.assertEqual("https://mcp.example.test/mcp", values["TRAVEL_BUDDY_MCP_URL"])

    def test_process_environment_overrides_azd_values(self) -> None:
        merged = merge_environment_values(
            {"AZURE_AI_MODEL_DEPLOYMENT_NAME": "candidate-model"},
            {"AZURE_AI_MODEL_DEPLOYMENT_NAME": "travel-model"},
        )

        self.assertEqual("candidate-model", merged["AZURE_AI_MODEL_DEPLOYMENT_NAME"])

    def test_post_provision_accepts_endpoint_alias_and_remote_mcp(self) -> None:
        checks = post_provision_checks(
            {
                "AZURE_AI_PROJECT_ENDPOINT": "https://example.test/projects/lab",
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": "travel-model",
                "SERVICE_MCP_SERVER_URI": "https://mcp.example.test",
            }
        )

        self.assertFalse(any(check.blocking for check in checks))

    def test_post_provision_accepts_azd_model_deployment_metadata(self) -> None:
        checks = post_provision_checks(
            {
                "FOUNDRY_PROJECT_ENDPOINT": "https://example.test/projects/lab",
                "AI_PROJECT_DEPLOYMENTS": '[{"name":"travel-model"}]',
                "SERVICE_MCP_SERVER_URI": "https://mcp.example.test",
            }
        )

        self.assertFalse(any(check.blocking for check in checks))

    def test_post_provision_rejects_missing_values_and_local_mcp(self) -> None:
        checks = post_provision_checks(
            {
                "FOUNDRY_PROJECT_ENDPOINT": "https://example.test/projects/lab",
                "TRAVEL_BUDDY_MCP_URL": "http://localhost:8000/mcp",
            }
        )

        blockers = {check.name for check in checks if check.blocking}
        self.assertEqual({"model-deployment", "remote-mcp-url"}, blockers)


if __name__ == "__main__":
    unittest.main()
