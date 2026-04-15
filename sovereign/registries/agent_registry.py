"""Agent registry — tracks all instantiated agents by ID."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Central registry of all active agent instances.

    Agents register themselves on creation and deregister on teardown.
    Used by the orchestrator to look up and dispatch to agents by ID.
    """

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}

    def register(self, agent: Any) -> None:
        """Register an agent. Skips silently on duplicate ID (idempotent)."""
        aid = agent.agent_id
        if aid in self._agents:
            logger.debug("Agent already registered, skipping: %s", aid)
            return
        self._agents[aid] = agent
        logger.debug("Registered agent: %s", aid)

    def get(self, agent_id: str) -> Any | None:
        """Return a registered agent by ID, or None if not found."""
        return self._agents.get(agent_id)

    def count(self) -> int:
        """Return the number of registered agents."""
        return len(self._agents)

    def deregister(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(agent_id, None)

    def list_agents(self) -> list[dict[str, Any]]:
        """Return descriptions of all registered agents."""
        return [a.describe() for a in self._agents.values()]

    def __len__(self) -> int:
        return len(self._agents)
