"""Operating modes layer — 16 mode configurations.

Simple modes (no extra logic) are defined inline via _mode().
Complex modes with custom behaviour live in their own files.
"""
from __future__ import annotations

from sovereign.kernel.action_classes import ActionClass
from sovereign.modes.base_mode import BaseMode
from sovereign.modes.emergency_mode import EmergencyMode
from sovereign.modes.founder_mode import FounderMode

# Richer modes with custom behaviour
from sovereign.modes.local_offline_mode import Local_offlineMode
from sovereign.modes.prestige_mode import PrestigeMode
from sovereign.modes.recovery_mode import RecoveryMode
from sovereign.modes.silent_mode import SilentMode
from sovereign.modes.war_mode import WarMode


def _mode(
    name: str,
    description: str,
    action_class: ActionClass = ActionClass.SUGGEST,
    threshold: float = 0.6,
    model: str = "claude-sonnet-4-6",
    offline_capable: bool = False,
    require_approval_for: list[str] | None = None,
) -> BaseMode:
    return BaseMode(
        name=name,
        description=description,
        default_action_class=action_class,
        escalation_threshold=threshold,
        preferred_model=model,
        offline_capable=offline_capable,
        require_approval_for=require_approval_for or [],
    )


# Registry of all available modes — keyed by mode name
MODES: dict[str, BaseMode] = {
    # ── Core modes ──────────────────────────────────────────────────────
    "command":  _mode("command",  "Direct task execution and system management",
                      ActionClass.EXECUTE, threshold=0.5),
    "business": _mode("business", "Business ops, communications, CRM, marketing, partnerships",
                      ActionClass.DRAFT,   threshold=0.4),
    "personal": _mode("personal", "Personal assistant: diary, routines, social, concierge",
                      ActionClass.SUGGEST, threshold=0.6),
    "finance":  _mode("finance",  "Financial analysis, budgeting, portfolio management",
                      ActionClass.SUGGEST, threshold=0.2, model="claude-opus-4-7"),
    "study":    _mode("study",    "Learning, research assistance, second brain",
                      ActionClass.SUGGEST, threshold=0.8),
    "travel":   _mode("travel",   "Travel planning, bookings, itineraries, logistics",
                      ActionClass.DRAFT,   threshold=0.5),
    "research": _mode("research", "Deep research, synthesis, analysis, citations",
                      ActionClass.DRAFT,   threshold=0.6, model="claude-opus-4-7"),
    "builder":  _mode("builder",  "Code generation, architecture, system building",
                      ActionClass.DRAFT,   threshold=0.5),
    "survival": _mode("survival", "Emergency mode with minimal resources and offline packs",
                      ActionClass.SUGGEST, threshold=0.9,
                      model="claude-haiku-4-5-20251001", offline_capable=True),
    # ── Offline ─────────────────────────────────────────────────────────
    "local_offline": Local_offlineMode(),
    # ── Extended modes ───────────────────────────────────────────────────
    "founder":   FounderMode(),
    "war":       WarMode(),
    "prestige":  PrestigeMode(),
    "silent":    SilentMode(),
    "recovery":  RecoveryMode(),
    "emergency": EmergencyMode(),
}

# Convenience aliases for the 9 inlined modes (backward compat)
CommandMode  = type("CommandMode",  (BaseMode,), {})
BusinessMode = type("BusinessMode", (BaseMode,), {})
PersonalMode = type("PersonalMode", (BaseMode,), {})
FinanceMode  = type("FinanceMode",  (BaseMode,), {})
StudyMode    = type("StudyMode",    (BaseMode,), {})
TravelMode   = type("TravelMode",   (BaseMode,), {})
ResearchMode = type("ResearchMode", (BaseMode,), {})
BuilderMode  = type("BuilderMode",  (BaseMode,), {})
SurvivalMode = type("SurvivalMode", (BaseMode,), {})

__all__ = [
    "BaseMode", "MODES",
    # Simple inlined modes
    "CommandMode", "BusinessMode", "PersonalMode", "FinanceMode",
    "StudyMode", "TravelMode", "ResearchMode", "BuilderMode", "SurvivalMode",
    # Complex modes with own files
    "Local_offlineMode", "FounderMode", "WarMode", "PrestigeMode",
    "SilentMode", "RecoveryMode", "EmergencyMode",
]
