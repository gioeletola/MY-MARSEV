"""
SimpleCenter — lightweight base class for all data-only operational centers.

The 17 thin centers inherit from this instead of repeating the same
route() / describe() boilerplate in every file.
"""
from __future__ import annotations

import logging


class SimpleCenter:
    """
    Base class for simple domain centers that only need keyword-based routing.

    Subclasses declare class attributes:
        CENTER_ID    str   — unique center identifier
        DESCRIPTION  str   — human-readable description
        PRIMARY_MODE str   — default operating mode
        AGENTS       list  — list of agent IDs managed by this center
        DOMAIN_MAP   dict  — keyword → agent_id routing table
        DEFAULT_AGENT str  — fallback when no keyword matches (optional)
    """

    CENTER_ID: str = ""
    DESCRIPTION: str = ""
    PRIMARY_MODE: str = "command"
    AGENTS: list[str] = []
    DOMAIN_MAP: dict[str, str] = {}
    DEFAULT_AGENT: str = ""

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

    def describe(self) -> dict:
        return {
            "center_id": self.CENTER_ID,
            "description": self.DESCRIPTION,
            "primary_mode": self.PRIMARY_MODE,
            "agents": self.AGENTS,
        }
