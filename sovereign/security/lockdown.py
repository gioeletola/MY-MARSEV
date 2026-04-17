"""
Emergency Lockdown Mode — system-wide threat-response controls for SOVEREIGN AI OS.

Lockdown levels (ascending severity):
  NORMAL    — no restrictions
  ELEVATED  — advisory; all actions still permitted
  HIGH      — EXECUTE actions are flagged but not blocked
  CRITICAL  — only READ actions pass; all others are blocked
  EMERGENCY — only READ actions pass; EXECUTE/DRAFT/SUGGEST are hard-blocked

State is persisted to data/memory/lockdown.json so a restart does not
silently reset an active emergency lockdown.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCKDOWN_PATH = Path("data/memory/lockdown.json")

# Action classes that are always blocked at CRITICAL and above.
_BLOCKED_AT_CRITICAL: frozenset[str] = frozenset(
    {"EXECUTE", "DRAFT", "SUGGEST", "WRITE", "DELETE", "MODIFY"}
)
# Action classes explicitly permitted at any level.
_ALWAYS_ALLOWED: frozenset[str] = frozenset({"READ"})


# ---------------------------------------------------------------------------
# Enumerations & data models
# ---------------------------------------------------------------------------


class LockdownLevel(IntEnum):
    """Ordered severity levels for system lockdown."""

    NORMAL = 0
    ELEVATED = 1
    HIGH = 2
    CRITICAL = 3
    EMERGENCY = 4


@dataclass
class LockdownState:
    """Snapshot of the current lockdown configuration."""

    level: int                  # stored as int for JSON round-trip
    reason: str
    activated_by: str
    activated_at: str
    auto_release_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> LockdownState:
        return LockdownState(**d)

    @property
    def lockdown_level(self) -> LockdownLevel:
        return LockdownLevel(self.level)


# ---------------------------------------------------------------------------
# Lockdown Manager
# ---------------------------------------------------------------------------


class LockdownManager:
    """Manage and evaluate system-wide lockdown state.

    Behaviour by level
    ------------------
    NORMAL / ELEVATED
        ``is_action_allowed`` returns *True* for everything.
    HIGH
        All actions still allowed; the caller can treat this as a warning
        signal. (Enforcement is the caller's responsibility at HIGH.)
    CRITICAL / EMERGENCY
        Only ``READ`` (and anything in ``_ALWAYS_ALLOWED``) is permitted.
        Every other action class is blocked.
    """

    def __init__(self, store_path: Path = _LOCKDOWN_PATH) -> None:
        self._path = store_path
        self._state: LockdownState | None = None
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def activate(
        self,
        level: LockdownLevel,
        reason: str,
        activated_by: str,
        duration_minutes: int = 0,
    ) -> LockdownState:
        """Raise the lockdown to *level*.

        If *duration_minutes* > 0 the ``auto_release_at`` timestamp is set,
        but automatic release is **not** enforced here — callers should
        periodically call :meth:`status` and act on the ``auto_release_at``
        field.  This keeps the module free of background threads.

        Downgrading the level (activating a lower level than current) is
        allowed but logged as a warning.
        """
        now = datetime.now(timezone.utc)
        current = self.current_level()
        if level < current:
            logger.warning(
                "Lockdown downgrade requested: current=%s requested=%s by=%s",
                current.name,
                level.name,
                activated_by,
            )

        auto_release_at = ""
        if duration_minutes > 0:
            from datetime import timedelta
            auto_release_at = (now + timedelta(minutes=duration_minutes)).isoformat()

        self._state = LockdownState(
            level=int(level),
            reason=reason,
            activated_by=activated_by,
            activated_at=now.isoformat(),
            auto_release_at=auto_release_at,
        )
        self._save()
        logger.critical(
            "Lockdown activated: level=%s reason=%s by=%s",
            level.name,
            reason,
            activated_by,
        )
        return self._state

    def deactivate(self, deactivated_by: str) -> None:
        """Return the system to NORMAL lockdown level."""
        previous = self.current_level()
        self._state = None
        self._save()
        logger.warning(
            "Lockdown deactivated: previous=%s by=%s", previous.name, deactivated_by
        )

    def current_level(self) -> LockdownLevel:
        """Return the active :class:`LockdownLevel` (NORMAL if none active)."""
        if self._state is None:
            return LockdownLevel.NORMAL
        return self._state.lockdown_level

    def is_action_allowed(self, action_class: str) -> bool:
        """Return *True* if *action_class* is permitted at the current level.

        At CRITICAL and EMERGENCY only READ (and other always-allowed classes)
        pass.  At HIGH and below every action is allowed.
        """
        level = self.current_level()
        action_upper = action_class.upper()

        # READ is always permitted.
        if action_upper in _ALWAYS_ALLOWED:
            return True

        if level >= LockdownLevel.CRITICAL:
            # Block everything except the always-allowed set.
            if action_upper in _BLOCKED_AT_CRITICAL:
                logger.warning(
                    "Action blocked by lockdown: action=%s level=%s",
                    action_class,
                    level.name,
                )
                return False
            # Unknown action classes are also blocked at CRITICAL+.
            return False

        # NORMAL / ELEVATED / HIGH — permit everything.
        return True

    def status(self) -> dict:
        """Return a serialisable snapshot of the current lockdown state."""
        level = self.current_level()
        base: dict = {
            "level": level.name,
            "level_value": int(level),
            "active": self._state is not None,
        }
        if self._state is not None:
            base.update(
                {
                    "reason": self._state.reason,
                    "activated_by": self._state.activated_by,
                    "activated_at": self._state.activated_at,
                    "auto_release_at": self._state.auto_release_at,
                }
            )
        return base

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            if data:
                self._state = LockdownState.from_dict(data)
                logger.info(
                    "Lockdown state restored: level=%s",
                    self._state.lockdown_level.name,
                )
        except Exception:
            logger.exception("Failed to load lockdown state; defaulting to NORMAL")

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._state.to_dict() if self._state is not None else {}
        self._path.write_text(json.dumps(payload, indent=2))
