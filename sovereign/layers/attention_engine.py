"""
Attention Engine Layer — protect, allocate, and optimize the user's attention.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AttentionSlot:
    """A protected block of the user's attention."""
    slot_id: str
    label: str
    category: str          # "deep_work" | "shallow" | "admin" | "recovery" | "social"
    priority: int          # 1 = highest
    allocated_minutes: int
    protected: bool = True
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AttentionAudit:
    """Weekly attention audit report."""
    period: str            # e.g. "2024-W12"
    deep_work_hours: float
    shallow_hours: float
    admin_hours: float
    recovery_hours: float
    top_attention_consumers: list[str]
    attention_leaks: list[str]
    recommendations: list[str]


class AttentionEngineLayer:
    """
    Manages the user's attention budget.

    - Maintains protected time slots
    - Tracks attention allocation
    - Detects attention leaks (low-ROI sinks)
    - Scores attention ROI
    """

    WEEKLY_HOURS = 168  # total hours in a week

    def __init__(self) -> None:
        self._slots: list[AttentionSlot] = []
        self._attention_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------

    def add_slot(self, slot: AttentionSlot) -> None:
        """Register a protected attention slot."""
        self._slots.append(slot)
        logger.debug("AttentionEngine: added slot %s (%s min)", slot.label, slot.allocated_minutes)

    def remove_slot(self, slot_id: str) -> bool:
        before = len(self._slots)
        self._slots = [s for s in self._slots if s.slot_id != slot_id]
        return len(self._slots) < before

    def log_attention(self, activity: str, minutes: int, category: str, roi: float) -> None:
        """Log actual attention spent on an activity."""
        self._attention_log.append({
            "activity": activity,
            "minutes": minutes,
            "category": category,
            "roi": roi,  # 0.0 – 1.0
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    def allocated_deep_work_minutes(self) -> int:
        return sum(
            s.allocated_minutes for s in self._slots
            if s.category == "deep_work" and s.protected
        )

    def detect_leaks(self, threshold: float = 0.3) -> list[str]:
        """Return activities with ROI below threshold."""
        return [
            entry["activity"]
            for entry in self._attention_log
            if entry.get("roi", 1.0) < threshold
        ]

    def generate_audit(self, period: str) -> AttentionAudit:
        """Generate an attention audit for a period."""
        def _hours(cat: str) -> float:
            return sum(
                e["minutes"] for e in self._attention_log if e.get("category") == cat
            ) / 60

        top_consumers: list[str] = []
        if self._attention_log:
            from collections import Counter
            counts = Counter(e["activity"] for e in self._attention_log)
            top_consumers = [a for a, _ in counts.most_common(5)]

        leaks = self.detect_leaks()

        recommendations: list[str] = []
        deep = _hours("deep_work")
        if deep < 10:
            recommendations.append(f"Deep work hours ({deep:.1f}h) below 10h target — protect more blocks.")
        if leaks:
            recommendations.append(f"Attention leaks detected: {', '.join(leaks[:3])} — consider eliminating.")

        return AttentionAudit(
            period=period,
            deep_work_hours=_hours("deep_work"),
            shallow_hours=_hours("shallow"),
            admin_hours=_hours("admin"),
            recovery_hours=_hours("recovery"),
            top_attention_consumers=top_consumers,
            attention_leaks=leaks,
            recommendations=recommendations,
        )

    def status(self) -> dict[str, Any]:
        return {
            "protected_slots": len(self._slots),
            "allocated_deep_work_minutes": self.allocated_deep_work_minutes(),
            "logged_entries": len(self._attention_log),
            "attention_leaks": self.detect_leaks(),
        }
