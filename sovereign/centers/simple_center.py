"""
SimpleCenter — lightweight base class for all data-only operational centers.

All centers inherit from this instead of repeating the same boilerplate.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any


class SimpleCenter:
    """
    Base class for SOVEREIGN operational centers.

    Subclasses declare class attributes:
        CENTER_ID    str   — unique center identifier
        DESCRIPTION  str   — human-readable description
        PRIMARY_MODE str   — default operating mode
        AGENTS       list  — list of agent IDs managed by this center
        DOMAIN_MAP   dict  — keyword → agent_id routing table
        DEFAULT_AGENT str  — fallback when no keyword matches (optional)
        CAPABILITIES list  — human-readable capability descriptions (optional)
    """

    CENTER_ID: str = ""
    DESCRIPTION: str = ""
    PRIMARY_MODE: str = "command"
    AGENTS: list[str] = []
    DOMAIN_MAP: dict[str, str] = {}
    DEFAULT_AGENT: str = ""
    CAPABILITIES: list[str] = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls._logger = logging.getLogger(cls.__module__)

    def route(self, objective: str) -> str:
        """Return the best-matching agent_id for the given objective string."""
        obj = objective.lower()
        for kw, agent_id in self.DOMAIN_MAP.items():
            if kw in obj:
                return agent_id
        return self.DEFAULT_AGENT or (self.AGENTS[0] if self.AGENTS else "")

    def route_keywords(self, keywords: list[str]) -> str:
        """Route from a list of intent keywords (used by orchestrator)."""
        for kw in keywords:
            if kw.lower() in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw.lower()]
        return self.DEFAULT_AGENT or (self.AGENTS[0] if self.AGENTS else "")

    async def dispatch(
        self,
        task: Any,
        ctx: Any,
        agent_registry: Any = None,
        intent_keywords: list[str] | None = None,
    ) -> Any:
        """
        Route a task to the correct agent and execute it.

        agent_registry must support .get(agent_id) → agent instance.
        """
        if agent_registry is None:
            raise RuntimeError(f"{self.CENTER_ID}: no agent_registry provided")

        agent_id = self.route_keywords(intent_keywords or []) or self.route(
            getattr(task, "objective", "")
        )
        agent = agent_registry.get(agent_id)
        if agent is None and self.DEFAULT_AGENT:
            agent = agent_registry.get(self.DEFAULT_AGENT)
        if agent is None and self.AGENTS:
            agent = agent_registry.get(self.AGENTS[0])
        if agent is None:
            raise RuntimeError(f"{self.CENTER_ID}: no agent found for id={agent_id!r}")

        self._logger.info("%s dispatching to agent=%s", self.CENTER_ID, agent_id)
        return await agent.run(task, ctx)

    def schedule(
        self,
        task_objective: str,
        cron: str = "0 9 * * 1",
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Register a recurring task schedule for this center.
        Returns a schedule descriptor (actual scheduling is handled by TaskScheduler).
        """
        return {
            "center_id": self.CENTER_ID,
            "task_objective": task_objective,
            "cron": cron,
            "agent_id": agent_id or self.DEFAULT_AGENT or (self.AGENTS[0] if self.AGENTS else ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def status(self) -> dict[str, Any]:
        """Return current center status snapshot."""
        return {
            "center_id": self.CENTER_ID,
            "description": self.DESCRIPTION,
            "primary_mode": self.PRIMARY_MODE,
            "agent_count": len(self.AGENTS),
            "domain_keywords": len(self.DOMAIN_MAP),
            "capabilities": self.CAPABILITIES or [f"Route to {len(self.AGENTS)} agents"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def list_capabilities(self) -> list[str]:
        """Return human-readable capability descriptions."""
        caps = list(self.CAPABILITIES)
        if not caps:
            caps = [f"Coordinates: {', '.join(self.AGENTS[:5])}{'...' if len(self.AGENTS) > 5 else ''}"]
        return caps

    def describe(self) -> dict:
        return {
            "center_id": self.CENTER_ID,
            "description": self.DESCRIPTION,
            "primary_mode": self.PRIMARY_MODE,
            "agents": self.AGENTS,
            "capabilities": self.list_capabilities(),
        }
