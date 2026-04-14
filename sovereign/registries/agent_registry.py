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
        """Register an agent. Raises ValueError on ID collision."""
        aid = agent.agent_id
        if aid in self._agents:
            raise ValueError(f"Agent '{aid}' is already registered.")
        self._agents[aid] = agent
        logger.debug("Registered agent", agent_id=aid)

    def get(self, agent_id: str) -> Any:
        """Return a registered agent by ID. Raises KeyError if not found."""
        try:
            return self._agents[agent_id]
        except KeyError:
            raise KeyError(
                f"Agent '{agent_id}' not found. Available: {list(self._agents)}"
            )

    def deregister(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        self._agents.pop(agent_id, None)

    def list_agents(self) -> list[dict[str, Any]]:
        """Return descriptions of all registered agents."""
        return [a.describe() for a in self._agents.values()]

    def __len__(self) -> int:
        return len(self._agents)
