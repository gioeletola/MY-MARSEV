"""Operating modes layer — 17 mode configurations.

Simple modes (no extra logic) are defined inline via _mode().
Complex modes with custom behaviour live in their own files.
"""
from __future__ import annotations

from sovereign.kernel.action_classes import ActionClass
from sovereign.modes.base_mode import BaseMode
from sovereign.modes.caveman_mode import CavemanMode
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


def _enrich_from_config() -> None:
    """Load config/operating_modes.yaml and validate MODES keys match."""
    import pathlib
    config_path = pathlib.Path("config/operating_modes.yaml")
    if not config_path.exists():
        return
    try:
        import yaml as _yaml
        data = _yaml.safe_load(config_path.read_text("utf-8")) or {}
        config_modes = set(data.get("modes", {}).keys())
        code_modes = set(MODES.keys())
        missing_in_code = config_modes - code_modes
        missing_in_config = code_modes - config_modes
        if missing_in_code:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "modes: config has modes not in code: %s", missing_in_code
            )
        if missing_in_config:
            import logging as _logging
            _logging.getLogger(__name__).debug(
                "modes: code has modes not in config: %s", missing_in_config
            )
    except Exception as _exc:
        import logging as _logging
        _logging.getLogger(__name__).debug("modes: could not load config: %s", _exc)


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
    # ── Offline / budget ────────────────────────────────────────────────
    "local_offline": Local_offlineMode(),
    "caveman":       CavemanMode(),
    # ── Extended modes ───────────────────────────────────────────────────
    "founder":   FounderMode(),
    "war":       WarMode(),
    "prestige":  PrestigeMode(),
    "silent":    SilentMode(),
    "recovery":  RecoveryMode(),
    "emergency": EmergencyMode(),
}

def validate_mode(name: str) -> bool:
    """Return True if *name* is a registered operating mode."""
    return name in MODES


_enrich_from_config()


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
    "BaseMode", "MODES", "validate_mode",
    # Simple inlined modes
    "CommandMode", "BusinessMode", "PersonalMode", "FinanceMode",
    "StudyMode", "TravelMode", "ResearchMode", "BuilderMode", "SurvivalMode",
    # Complex modes with own files
    "CavemanMode", "Local_offlineMode", "FounderMode", "WarMode", "PrestigeMode",
    "SilentMode", "RecoveryMode", "EmergencyMode",
]
