from __future__ import annotations

from typing import Any

from .config import TravelBuddySettings


def configure_observability(settings: TravelBuddySettings) -> bool:
    connection_string = settings.app_insights_connection_string
    if not connection_string:
        return False
    try:
        from agent_framework import settings as agent_framework_settings
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError as exc:
        raise RuntimeError(
            "Install azure-monitor-opentelemetry and Agent Framework to enable telemetry."
        ) from exc

    agent_framework_settings.tracing_implementation = "opentelemetry"
    configure_azure_monitor(connection_string=connection_string)
    return True


def get_tracer() -> Any:
    from opentelemetry import trace

    return trace.get_tracer("travel_buddy")
