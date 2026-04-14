"""
Action class hierarchy for the SOVEREIGN AI OS.

Defines the ordered permission levels for agent actions.
Higher values require higher authority and/or explicit human approval.
"""
from __future__ import annotations

from enum import IntEnum


class ActionClass(IntEnum):
    """
    Ordered hierarchy of agent action capabilities.

    READ    — Observe, retrieve, analyze. No side effects.
    SUGGEST — Produce recommendations or drafts for human review. No side effects.
    DRAFT   — Create artifacts (files, code, plans) but do not deploy or send.
    EXECUTE — Perform side-effecting operations: send messages, call APIs, run code,
              modify external state.

    The system's global ceiling is set by SovereignConfig.max_action_class.
    Individual agents may have a lower ceiling defined in their AgentSpec or registry entry.
    """

    READ = 1
    SUGGEST = 2
    DRAFT = 3
    EXECUTE = 4

    def requires_approval(self, threshold: ActionClass) -> bool:
        """Return True if this action class exceeds the configured approval threshold."""
        return self > threshold

    def label(self) -> str:
        """Return a human-readable label for display and logging."""
        return self.name.capitalize()

    @classmethod
    def from_str(cls, value: str) -> ActionClass:
        """Parse an ActionClass from a case-insensitive string (e.g. 'execute')."""
        try:
            return cls[value.upper()]
        except KeyError:
            raise ValueError(
                f"Unknown action class '{value}'. "
                f"Valid values: {[m.name for m in cls]}"
            )
