"""
Agent Factory — creates, tracks, and destroys ephemeral sub-agents.
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.factory.agent_spec import AgentSpec
from sovereign.swarm.ephemeral_agent import EphemeralAgent

logger = logging.getLogger(__name__)

MAX_CONCURRENT_EPHEMERAL = 10


class AgentFactory:
    """
    Manages the lifecycle of ephemeral sub-agents.

    Enforces a concurrency limit (MAX_CONCURRENT_EPHEMERAL) to prevent
    unbounded resource consumption.
    """

    def __init__(
        self,
        claude_client: Any,
        tool_registry: Any,
        memory_manager: Any,
        constitution: Any,
        prompt_builder: Any,
        agent_registry: Any,
    ) -> None:
        self._claude = claude_client
        self._tools = tool_registry
        self._memory = memory_manager
        self._constitution = constitution
        self._prompt_builder = prompt_builder
        self._agent_registry = agent_registry
        self._active: dict[str, EphemeralAgent] = {}

    async def spawn(self, spec: AgentSpec) -> EphemeralAgent:
        """
        Validate the spec, instantiate an EphemeralAgent, register it, and return it.

        Raises:
            ValueError: If spec is invalid or concurrency limit exceeded.
        """
        spec.validate()

        if len(self._active) >= MAX_CONCURRENT_EPHEMERAL:
            raise ValueError(
                f"Concurrency limit reached ({MAX_CONCURRENT_EPHEMERAL}). "
                "Despawn an agent before spawning a new one."
            )

        agent = EphemeralAgent(
            spec=spec,
            claude_client=self._claude,
            tool_registry=self._tools,
            memory_manager=self._memory,
            constitution=self._constitution,
            prompt_builder=self._prompt_builder,
        )
        self._active[agent.agent_id] = agent

        try:
            self._agent_registry.register(agent)
        except ValueError:
            pass  # Already registered (e.g., in tests)

        logger.info("Spawned ephemeral agent", agent_id=agent.agent_id, spec=spec.name)
        return agent

    async def despawn(self, agent_id: str) -> None:
        """Deregister and clean up an ephemeral agent."""
        self._active.pop(agent_id, None)
        try:
            self._agent_registry.deregister(agent_id)
        except Exception:
            pass
        logger.info("Despawned ephemeral agent", agent_id=agent_id)

    def list_active(self) -> list[str]:
        """Return IDs of all currently active ephemeral agents."""
        return list(self._active)

    def get(self, agent_id: str) -> EphemeralAgent:
        try:
            return self._active[agent_id]
        except KeyError:
            raise KeyError(f"Ephemeral agent '{agent_id}' is not active.")
