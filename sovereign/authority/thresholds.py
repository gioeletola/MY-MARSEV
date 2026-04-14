"""Escalation thresholds — per-mode configuration for autonomous vs. human decisions."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EscalationThresholds:
    """
    Defines when an agent must escalate vs. proceed autonomously.

    risk scores are floats in [0.0, 1.0]:
      0.0 = no risk   1.0 = maximum risk

    The GuardianAgent scores each action; if score >= escalate_above_risk,
    it triggers the ApprovalGate.
    """

    auto_approve_below_risk: float = 0.2
    escalate_above_risk: float = 0.7
    max_autonomous_action_class: str = "SUGGEST"
    require_human_for_financial: bool = True
    require_human_for_external_api: bool = False
    require_human_for_file_delete: bool = True
    require_human_for_irreversible: bool = True

    def should_auto_approve(self, risk_score: float) -> bool:
        return risk_score < self.auto_approve_below_risk

    def should_escalate(self, risk_score: float) -> bool:
        return risk_score >= self.escalate_above_risk

    @classmethod
    def for_mode(cls, mode_name: str) -> EscalationThresholds:
        """Return mode-specific thresholds."""
        presets: dict[str, dict] = {
            "command":       {"auto_approve_below_risk": 0.3, "escalate_above_risk": 0.7, "max_autonomous_action_class": "EXECUTE"},
            "business":      {"auto_approve_below_risk": 0.2, "escalate_above_risk": 0.6, "require_human_for_external_api": True},
            "personal":      {"auto_approve_below_risk": 0.3, "escalate_above_risk": 0.7},
            "finance":       {"auto_approve_below_risk": 0.05, "escalate_above_risk": 0.3, "require_human_for_financial": True},
            "study":         {"auto_approve_below_risk": 0.4, "escalate_above_risk": 0.8},
            "travel":        {"auto_approve_below_risk": 0.2, "escalate_above_risk": 0.6},
            "research":      {"auto_approve_below_risk": 0.3, "escalate_above_risk": 0.7},
            "builder":       {"auto_approve_below_risk": 0.2, "escalate_above_risk": 0.6},
            "local_offline": {"auto_approve_below_risk": 0.3, "escalate_above_risk": 0.8},
            "survival":      {"auto_approve_below_risk": 0.5, "escalate_above_risk": 0.9},
        }
        kwargs = presets.get(mode_name, {})
        return cls(**kwargs)
