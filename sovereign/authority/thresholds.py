"""
Escalation thresholds — per-mode configuration for autonomous vs. human decisions.

New features:
  - EscalationThresholds.get_threshold(mode, action_class) → float
  - EscalationThresholds.adjust(mode, action_class, delta)   — dynamic feedback
  - EscalationThresholds.for_mode(mode_name) → EscalationThresholds
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Default per-mode, per-action-class confidence thresholds for auto-execution
# ---------------------------------------------------------------------------

_DEFAULT_THRESHOLDS: dict[str, dict[str, float]] = {
    #  mode          → { action_class → confidence_threshold_for_auto_exec }
    "command":       {"SUGGEST": 0.5, "PLAN": 0.6, "EXECUTE": 0.7, "WRITE": 0.65, "DELETE": 0.85},
    "business":      {"SUGGEST": 0.6, "PLAN": 0.65, "EXECUTE": 0.75, "WRITE": 0.70, "DELETE": 0.90},
    "personal":      {"SUGGEST": 0.5, "PLAN": 0.6, "EXECUTE": 0.70, "WRITE": 0.65, "DELETE": 0.88},
    "finance":       {"SUGGEST": 0.7, "PLAN": 0.80, "EXECUTE": 0.90, "WRITE": 0.85, "DELETE": 0.95},
    "study":         {"SUGGEST": 0.4, "PLAN": 0.5, "EXECUTE": 0.65, "WRITE": 0.60, "DELETE": 0.85},
    "travel":        {"SUGGEST": 0.5, "PLAN": 0.6, "EXECUTE": 0.70, "WRITE": 0.65, "DELETE": 0.88},
    "research":      {"SUGGEST": 0.5, "PLAN": 0.6, "EXECUTE": 0.70, "WRITE": 0.65, "DELETE": 0.88},
    "builder":       {"SUGGEST": 0.5, "PLAN": 0.6, "EXECUTE": 0.72, "WRITE": 0.67, "DELETE": 0.88},
    "local_offline": {"SUGGEST": 0.4, "PLAN": 0.5, "EXECUTE": 0.65, "WRITE": 0.60, "DELETE": 0.85},
    "survival":      {"SUGGEST": 0.3, "PLAN": 0.4, "EXECUTE": 0.55, "WRITE": 0.50, "DELETE": 0.75},
    "founder":       {"SUGGEST": 0.5, "PLAN": 0.6, "EXECUTE": 0.72, "WRITE": 0.67, "DELETE": 0.88},
    "war":           {"SUGGEST": 0.3, "PLAN": 0.4, "EXECUTE": 0.55, "WRITE": 0.50, "DELETE": 0.70},
    "prestige":      {"SUGGEST": 0.6, "PLAN": 0.7, "EXECUTE": 0.80, "WRITE": 0.75, "DELETE": 0.92},
    "silent":        {"SUGGEST": 0.7, "PLAN": 0.8, "EXECUTE": 0.90, "WRITE": 0.85, "DELETE": 0.97},
    "recovery":      {"SUGGEST": 0.5, "PLAN": 0.6, "EXECUTE": 0.70, "WRITE": 0.65, "DELETE": 0.88},
    "emergency":     {"SUGGEST": 0.3, "PLAN": 0.4, "EXECUTE": 0.50, "WRITE": 0.45, "DELETE": 0.70},
    # default (all modes not listed above)
    "default":       {"SUGGEST": 0.5, "PLAN": 0.6, "EXECUTE": 0.72, "WRITE": 0.67, "DELETE": 0.88},
}


@dataclass
class EscalationThresholds:
    """
    Defines when an agent must escalate vs. proceed autonomously.

    Risk scores are floats in [0.0, 1.0]:
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

    # Per-(mode, action_class) dynamic thresholds — overrides _DEFAULT_THRESHOLDS
    _dynamic_overrides: dict[str, dict[str, float]] = field(
        default_factory=dict, repr=False
    )

    def should_auto_approve(self, risk_score: float) -> bool:
        return risk_score < self.auto_approve_below_risk

    def should_escalate(self, risk_score: float) -> bool:
        return risk_score >= self.escalate_above_risk

    # -------------------------------------------------------------------------
    # Per-mode, per-action-class threshold API
    # -------------------------------------------------------------------------

    def get_threshold(self, mode: str, action_class: str) -> float:
        """
        Return the confidence threshold required for auto-execution.

        A value of 0.8 means the agent must have >= 0.8 confidence before
        executing autonomously in this mode for this action class.

        Args:
            mode         – operating mode name (e.g. "finance", "command")
            action_class – action class name (e.g. "EXECUTE", "SUGGEST")

        Returns:
            float in [0.0, 1.0]
        """
        # Dynamic overrides take priority
        overrides = self._dynamic_overrides.get(mode, {})
        if action_class in overrides:
            return overrides[action_class]

        mode_thresholds = _DEFAULT_THRESHOLDS.get(mode, _DEFAULT_THRESHOLDS["default"])
        return mode_thresholds.get(action_class, 0.7)

    def adjust(self, mode: str, action_class: str, delta: float) -> float:
        """
        Dynamically adjust a threshold based on feedback.

        Positive delta = raise the bar (more caution).
        Negative delta = lower the bar (more autonomy).

        Returns the new threshold value (clamped to [0.0, 1.0]).
        """
        current = self.get_threshold(mode, action_class)
        new_value = max(0.0, min(1.0, current + delta))
        if mode not in self._dynamic_overrides:
            self._dynamic_overrides[mode] = {}
        self._dynamic_overrides[mode][action_class] = new_value
        return new_value

    def reset_overrides(self, mode: str | None = None) -> None:
        """Reset dynamic overrides for a mode (or all modes if None)."""
        if mode is None:
            self._dynamic_overrides.clear()
        else:
            self._dynamic_overrides.pop(mode, None)

    def all_thresholds(self, mode: str) -> dict[str, float]:
        """Return full action_class → threshold dict for a mode."""
        base = dict(_DEFAULT_THRESHOLDS.get(mode, _DEFAULT_THRESHOLDS["default"]))
        base.update(self._dynamic_overrides.get(mode, {}))
        return base

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def reset_to_defaults(self) -> None:
        """Reset all dynamic overrides and scalar thresholds to factory defaults."""
        self._dynamic_overrides.clear()
        self.auto_approve_below_risk = 0.2
        self.escalate_above_risk = 0.7
        self.max_autonomous_action_class = "SUGGEST"
        self.require_human_for_financial = True
        self.require_human_for_external_api = False
        self.require_human_for_file_delete = True
        self.require_human_for_irreversible = True

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON persistence."""
        return {
            "auto_approve_below_risk": self.auto_approve_below_risk,
            "escalate_above_risk": self.escalate_above_risk,
            "max_autonomous_action_class": self.max_autonomous_action_class,
            "require_human_for_financial": self.require_human_for_financial,
            "require_human_for_external_api": self.require_human_for_external_api,
            "require_human_for_file_delete": self.require_human_for_file_delete,
            "require_human_for_irreversible": self.require_human_for_irreversible,
            "_dynamic_overrides": dict(self._dynamic_overrides),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EscalationThresholds":
        """Restore from a dict produced by ``to_dict()``."""
        overrides = data.pop("_dynamic_overrides", {})
        obj = cls(
            auto_approve_below_risk=data.get("auto_approve_below_risk", 0.2),
            escalate_above_risk=data.get("escalate_above_risk", 0.7),
            max_autonomous_action_class=data.get("max_autonomous_action_class", "SUGGEST"),
            require_human_for_financial=data.get("require_human_for_financial", True),
            require_human_for_external_api=data.get("require_human_for_external_api", False),
            require_human_for_file_delete=data.get("require_human_for_file_delete", True),
            require_human_for_irreversible=data.get("require_human_for_irreversible", True),
        )
        obj._dynamic_overrides = overrides
        return obj

    # -------------------------------------------------------------------------
    # Factory
    # -------------------------------------------------------------------------

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
            "founder":       {"auto_approve_below_risk": 0.2, "escalate_above_risk": 0.6},
            "war":           {"auto_approve_below_risk": 0.5, "escalate_above_risk": 0.85},
            "prestige":      {"auto_approve_below_risk": 0.15, "escalate_above_risk": 0.5},
            "silent":        {"auto_approve_below_risk": 0.1, "escalate_above_risk": 0.4},
            "recovery":      {"auto_approve_below_risk": 0.3, "escalate_above_risk": 0.7},
            "emergency":     {"auto_approve_below_risk": 0.5, "escalate_above_risk": 0.9},
        }
        kwargs = presets.get(mode_name, {})
        return cls(**kwargs)
