import unittest
from unittest.mock import patch

from travel_buddy.config import TravelBuddySettings
from travel_buddy.observability import configure_observability


class ObservabilityTests(unittest.TestCase):
    def test_observability_is_disabled_without_connection_string(self) -> None:
        settings = TravelBuddySettings(None, None)

        self.assertFalse(configure_observability(settings))

    def test_observability_configures_azure_monitor_and_agent_framework(self) -> None:
        settings = TravelBuddySettings(None, None, app_insights_connection_string="connection")

        with (
            patch(
                "azure.monitor.opentelemetry.configure_azure_monitor"
            ) as configure_azure_monitor,
            patch("agent_framework.observability.enable_instrumentation") as enable_instrumentation,
        ):
            self.assertTrue(configure_observability(settings))

        configure_azure_monitor.assert_called_once_with(connection_string="connection")
        enable_instrumentation.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
