"""Adaptive silence — suppresses non-critical interrupts during detected focus time."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class FocusLevel(str, Enum):
    IDLE      = "idle"       # user absent or inactive
    AVAILABLE = "available"  # normal interrupts allowed
    SOFT      = "soft"       # suppress low-priority notifications
    DEEP      = "deep"       # suppress all non-critical notifications
    LOCKED    = "locked"     # emergency-only (manual override)


@dataclass
class FocusWindow:
    start_ts: float
    end_ts: float
    level: FocusLevel
    trigger: str   # "presence" | "manual" | "schedule" | "inactivity"


@dataclass
class SilenceConfig:
    deep_focus_threshold_s: float = 600.0    # 10 min continuous activity → deep focus
    idle_threshold_s: float = 120.0          # 2 min no activity → idle
    soft_focus_inactivity_s: float = 30.0    # 30s no interaction → soft focus
    min_priority_for_deep: float = 0.9       # only show suggestions with priority ≥ this in deep focus
    min_priority_for_soft: float = 0.6


class AdaptiveSilence:
    """
    Monitors user activity signals and adjusts the focus level dynamically.

    Input signals:
    - ``record_activity()``  — called whenever user interacts (keypress, chat, etc.)
    - ``record_absence()``   — called by presence_detector when face not detected
    - ``set_manual()``       — user explicitly sets focus level

    Output:
    - ``should_interrupt(priority)`` — returns True if the notification should be shown
    - ``current_level``              — the current FocusLevel
    - ``run_loop()``                 — background loop that transitions levels over time
    """

    def __init__(self, config: SilenceConfig | None = None) -> None:
        self._config = config or SilenceConfig()
        self._level: FocusLevel = FocusLevel.AVAILABLE
        self._last_activity: float = time.time()
        self._last_absence: float = 0.0
        self._activity_streak_start: float = time.time()
        self._manual_override: FocusLevel | None = None
        self._manual_until: float = 0.0
        self._history: list[FocusWindow] = []
        self._level_start: float = time.time()
        self._callbacks: list[Callable[[FocusLevel], None]] = []
        self._running = False

    # ------------------------------------------------------------------
    # Signal inputs
    # ------------------------------------------------------------------

    def record_activity(self) -> None:
        """Call whenever the user interacts (keystroke, message sent, mouse move)."""
        self._last_activity = time.time()

    def record_absence(self) -> None:
        """Call when presence detector reports no face / no activity."""
        self._last_absence = time.time()

    def set_manual(self, level: FocusLevel, duration_s: float = 3600.0) -> None:
        """User manually sets focus level (overrides automatic detection)."""
        self._manual_override = level
        self._manual_until = time.time() + duration_s
        self._transition(level, trigger="manual")
        logger.info("AdaptiveSilence: manual override → %s for %.0fs", level.value, duration_s)

    def clear_manual(self) -> None:
        self._manual_override = None
        self._manual_until = 0.0

    # ------------------------------------------------------------------
    # Decision API
    # ------------------------------------------------------------------

    @property
    def current_level(self) -> FocusLevel:
        return self._level

    def should_interrupt(self, priority: float) -> bool:
        """Return True if a notification with this priority should be shown now."""
        lvl = self._level
        if lvl == FocusLevel.LOCKED:
            return priority >= 1.0  # only absolute critical
        if lvl == FocusLevel.DEEP:
            return priority >= self._config.min_priority_for_deep
        if lvl == FocusLevel.SOFT:
            return priority >= self._config.min_priority_for_soft
        if lvl == FocusLevel.IDLE:
            return False  # user is away, queue it
        return True  # AVAILABLE

    def on_level_change(self, callback: Callable[[FocusLevel], None]) -> None:
        self._callbacks.append(callback)

    # ------------------------------------------------------------------
    # Background evaluation loop
    # ------------------------------------------------------------------

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        self._running = True
        logger.info("AdaptiveSilence: background loop started")
        while self._running:
            if stop_event and stop_event.is_set():
                break
            self._evaluate()
            await asyncio.sleep(5.0)

    def stop(self) -> None:
        self._running = False

    def _evaluate(self) -> None:
        now = time.time()

        # Expire manual override
        if self._manual_override and now > self._manual_until:
            self._manual_override = None

        if self._manual_override:
            if self._level != self._manual_override:
                self._transition(self._manual_override, trigger="manual")
            return

        since_activity = now - self._last_activity
        since_absence  = now - self._last_absence

        # Determine target level
        if since_activity < 2.0:
            # Very recent activity
            streak = now - self._activity_streak_start
            if streak >= self._config.deep_focus_threshold_s:
                target = FocusLevel.DEEP
            else:
                target = FocusLevel.AVAILABLE
        elif since_activity < self._config.soft_focus_inactivity_s:
            target = FocusLevel.AVAILABLE
        elif since_activity < self._config.idle_threshold_s:
            target = FocusLevel.SOFT
        else:
            target = FocusLevel.IDLE

        # Reset streak on absence
        if self._last_absence > 0 and since_absence < 5.0:
            self._activity_streak_start = now

        if target != self._level:
            self._transition(target, trigger="presence")

    def _transition(self, new_level: FocusLevel, trigger: str) -> None:
        prev = self._level
        self._history.append(FocusWindow(
            start_ts=self._level_start,
            end_ts=time.time(),
            level=prev,
            trigger=trigger,
        ))
        if len(self._history) > 500:
            self._history = self._history[-500:]
        self._level = new_level
        self._level_start = time.time()
        logger.info(
            "AdaptiveSilence: %s → %s (trigger=%s)",
            prev.value, new_level.value, trigger,
        )
        for cb in self._callbacks:
            try:
                cb(new_level)
            except Exception as exc:
                logger.debug("AdaptiveSilence callback error: %s", exc)

    def summary(self) -> dict:
        return {
            "level": self._level.value,
            "manual_override": self._manual_override.value if self._manual_override else None,
            "since_last_activity_s": round(time.time() - self._last_activity, 1),
            "activity_streak_s": round(time.time() - self._activity_streak_start, 1),
            "history_count": len(self._history),
        }
