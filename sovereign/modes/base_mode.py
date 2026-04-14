"""Base operating mode — all modes inherit from this."""
from __future__ import annotations

from dataclasses import dataclass, field
from sovereign.kernel.action_classes import ActionClass


@dataclass
class BaseMode:
    """
    Defines the configuration for a SOVEREIGN AI OS operating mode.

    Each mode alters: active agents, decision priority, tone, response
    structure, risk tolerance, memory weighting, and tool routing.
    """

    name: str
    description: str
    default_action_class: ActionClass = ActionClass.SUGGEST
    escalation_threshold: float = 0.6
    preferred_model: str = "claude-sonnet-4-6"
    offline_capable: bool = False
    require_approval_for: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "default_action_class": self.default_action_class.name,
            "escalation_threshold": self.escalation_threshold,
            "preferred_model": self.preferred_model,
            "offline_capable": self.offline_capable,
            "require_approval_for": self.require_approval_for,
        }

    @classmethod
    def get_mode(cls, name: str) -> "BaseMode":
        """Look up a mode by name from the MODES registry."""
        from sovereign.modes import MODES
        try:
            return MODES[name]
        except KeyError:
            raise ValueError(f"Unknown mode '{name}'. Available: {list(MODES)}")
