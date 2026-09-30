from __future__ import annotations

from typing import Any

from agent_framework import AgentExecutor


class ContextPreservingAgentExecutor(AgentExecutor):
    def _restore_context_if_empty(self) -> None:
        if not self._cache and self._full_conversation:
            self._cache.extend(self._full_conversation)

    async def _run_agent_and_emit(self, ctx: Any) -> None:
        # Group chat excludes the last speaker from its own response broadcast.
        # Restore retained context if the orchestrator selects that speaker again.
        self._restore_context_if_empty()
        await super()._run_agent_and_emit(ctx)
