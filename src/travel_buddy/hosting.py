from __future__ import annotations

from .config import TravelBuddySettings
from .observability import configure_observability
from .workflow import build_travel_buddy


def run_host() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    settings = TravelBuddySettings.from_env()
    settings.require_cloud()
    configure_observability(settings)
    built = build_travel_buddy(settings)

    try:
        from agent_framework.foundry import ResponsesHostServer
    except ImportError as exc:
        raise RuntimeError(
            "Install agent-framework-foundry before starting the hosted agent."
        ) from exc

    ResponsesHostServer(built.agent).run()
