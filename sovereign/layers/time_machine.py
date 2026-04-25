"""
Time Machine Layer — temporal intelligence: learn from past, model future.
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/memory/time_machine.jsonl")


@dataclass
class TemporalEvent:
    """A recorded event with outcome tracking."""
    event_id: str
    event_type: str          # "decision" | "action" | "outcome" | "pattern"
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""        # filled in retrospectively
    outcome_score: float = 0.0   # -1.0 bad → +1.0 excellent
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    horizon: str = "present"  # "past" | "present" | "future"


class TimeMachineLayer:
    """
    Append-only temporal event log with pattern detection.

    Supports:
    - Recording events/decisions as they happen
    - Tagging outcomes retrospectively
    - Querying patterns by type, date range, or keyword
    - Computing decision quality score over time
    """

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._events: list[TemporalEvent] = []
        self._load()

    # ------------------------------------------------------------------

    def record(self, event: TemporalEvent) -> None:
        """Append a temporal event to the log."""
        self._events.append(event)
        self._append_to_disk(event)
        logger.debug("TimeMachine recorded event_id=%s type=%s", event.event_id, event.event_type)

    def tag_outcome(self, event_id: str, outcome: str, score: float) -> bool:
        """Retrospectively tag the outcome of a past event."""
        for ev in self._events:
            if ev.event_id == event_id:
                ev.outcome = outcome
                ev.outcome_score = max(-1.0, min(1.0, score))
                self._rewrite()
                return True
        return False

    def query(
        self,
        event_type: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Filter events by type or keyword."""
        results = self._events
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if keyword:
            kw = keyword.lower()
            results = [e for e in results if kw in e.description.lower()]
        return [asdict(e) for e in results[-limit:]]

    def decision_quality_score(self) -> float:
        """Mean outcome score across all tagged decisions."""
        decisions = [
            e for e in self._events
            if e.event_type == "decision" and e.outcome != ""
        ]
        if not decisions:
            return 0.0
        return sum(e.outcome_score for e in decisions) / len(decisions)

    def detect_patterns(self, window: int = 30) -> list[str]:
        """Naive pattern detection: return repeated event descriptions."""
        from collections import Counter
        recent = self._events[-window:]
        descriptions = [e.description[:60] for e in recent]
        counts = Counter(descriptions)
        return [desc for desc, cnt in counts.items() if cnt >= 2]

    def summary(self) -> dict[str, Any]:
        return {
            "total_events": len(self._events),
            "decision_quality_score": self.decision_quality_score(),
            "event_types": list({e.event_type for e in self._events}),
        }

    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._events.append(TemporalEvent(**json.loads(line)))
            logger.info("TimeMachine loaded %d events", len(self._events))
        except Exception as exc:
            logger.warning("TimeMachine load error: %s", exc)

    def _append_to_disk(self, event: TemporalEvent) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event), default=str) + "\n")
        except Exception as exc:
            logger.error("TimeMachine append failed: %s", exc)

    def _rewrite(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as f:
                for ev in self._events:
                    f.write(json.dumps(asdict(ev), default=str) + "\n")
        except Exception as exc:
            logger.error("TimeMachine rewrite failed: %s", exc)
