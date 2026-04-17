"""
Escalation chain for SOVEREIGN AI OS.

Determines the authority level required to proceed with an agent action
and maintains an auditable log of escalation events.

Persists events to data/ledger/escalations.jsonl.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ESCALATIONS_PATH = Path("data/ledger/escalations.jsonl")

# ---------------------------------------------------------------------------
# Risk-score thresholds that map to escalation levels
# ---------------------------------------------------------------------------

# (inclusive lower bound → level)
_RISK_THRESHOLDS = [
    (0.9, "OWNER"),
    (0.7, "ADMIN"),
    (0.4, "OPERATOR"),
    (0.0, "AUTO"),
]

# Action classes that always require at least OPERATOR review
_HIGH_STAKES_ACTION_CLASSES = frozenset({"EXECUTE", "DEPLOY", "DELETE", "FINANCE"})


# ---------------------------------------------------------------------------
# Enums & Dataclasses
# ---------------------------------------------------------------------------


class EscalationLevel(IntEnum):
    AUTO = 1      # System can proceed autonomously
    OPERATOR = 2  # Operator review required
    ADMIN = 3     # Admin approval required
    OWNER = 4     # Owner approval required


@dataclass
class EscalationEvent:
    """Immutable record of one escalation trigger."""

    event_id: str
    trigger: str                   # Free-text description of what triggered escalation
    agent_id: str
    action_class: str              # String label, e.g. "EXECUTE"
    risk_score: float
    level: EscalationLevel
    resolved: bool = False
    resolution: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trigger": self.trigger,
            "agent_id": self.agent_id,
            "action_class": self.action_class,
            "risk_score": self.risk_score,
            "level": self.level.name,
            "resolved": self.resolved,
            "resolution": self.resolution,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EscalationEvent:
        return cls(
            event_id=data["event_id"],
            trigger=data["trigger"],
            agent_id=data["agent_id"],
            action_class=data["action_class"],
            risk_score=data["risk_score"],
            level=EscalationLevel[data["level"]],
            resolved=data.get("resolved", False),
            resolution=data.get("resolution", ""),
            created_at=data.get("created_at", ""),
        )


# ---------------------------------------------------------------------------
# EscalationChain
# ---------------------------------------------------------------------------


class EscalationChain:
    """
    Evaluates the required approval level for an agent action and keeps
    a ledger of pending / resolved escalation events.

    Usage::

        chain = EscalationChain()
        level = chain.evaluate("agent-42", "EXECUTE", risk_score=0.75, objective="send email")
        if level > EscalationLevel.AUTO:
            event = chain.create_event("risk>threshold", "agent-42", "EXECUTE", 0.75, level)
    """

    def __init__(self, persist_path: Path | None = None, notification_service: Any = None) -> None:
        self._path: Path = persist_path or _ESCALATIONS_PATH
        self._events: dict[str, EscalationEvent] = {}
        self._notif = notification_service
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        agent_id: str,
        action_class: str,
        risk_score: float,
        objective: str = "",
    ) -> EscalationLevel:
        """
        Compute the minimum EscalationLevel required.

        Rules (in priority order):
        1. risk_score >= 0.9 → OWNER
        2. risk_score >= 0.7 → ADMIN
        3. action_class in high-stakes set → at least OPERATOR
        4. risk_score >= 0.4 → OPERATOR
        5. Otherwise → AUTO
        """
        risk_score = max(0.0, min(1.0, risk_score))

        # Risk-score based floor
        for threshold, level_name in _RISK_THRESHOLDS:
            if risk_score >= threshold:
                level = EscalationLevel[level_name]
                break
        else:
            level = EscalationLevel.AUTO

        # Action-class override: at minimum OPERATOR for high-stakes classes
        if action_class.upper() in _HIGH_STAKES_ACTION_CLASSES:
            level = max(level, EscalationLevel.OPERATOR)

        logger.debug(
            "EscalationChain.evaluate: agent=%s action=%s risk=%.2f → %s",
            agent_id, action_class, risk_score, level.name,
        )
        return level

    def create_event(
        self,
        trigger: str,
        agent_id: str,
        action_class: str,
        risk_score: float,
        level: EscalationLevel,
    ) -> EscalationEvent:
        """Create, persist, and return a new EscalationEvent."""
        event = EscalationEvent(
            event_id=str(uuid.uuid4()),
            trigger=trigger,
            agent_id=agent_id,
            action_class=action_class,
            risk_score=risk_score,
            level=level,
        )
        self._events[event.event_id] = event
        self._append(event)
        logger.info(
            "EscalationChain: new event %s — level=%s agent=%s",
            event.event_id[:8], level.name, agent_id,
        )
        # Push notification for ADMIN/OWNER escalations
        if self._notif and level >= EscalationLevel.ADMIN:
            import asyncio
            try:
                asyncio.get_event_loop().create_task(
                    self._notif.send(
                        title=f"Escalation: {level.name} required",
                        body=f"Agent {agent_id} triggered {level.name} escalation. Risk: {risk_score:.0%}. Trigger: {trigger}",
                        level="critical" if level == EscalationLevel.OWNER else "warning",
                        source_agent=agent_id,
                    )
                )
            except Exception:
                pass
        return event

    def resolve(self, event_id: str, resolution: str) -> bool:
        """
        Mark an escalation event as resolved.

        Returns True if the event existed and was unresolved.
        """
        event = self._events.get(event_id)
        if event is None:
            logger.warning("EscalationChain.resolve: unknown event_id '%s'", event_id)
            return False
        if event.resolved:
            return False
        event.resolved = True
        event.resolution = resolution
        self._append(event)          # Append updated snapshot
        del self._events[event_id]   # Remove from pending cache
        logger.info("EscalationChain: resolved event %s — %s", event_id[:8], resolution)
        return True

    def pending_events(self) -> list[EscalationEvent]:
        """Return all unresolved escalation events, oldest first."""
        return sorted(self._events.values(), key=lambda e: e.created_at)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _append(self, event: EscalationEvent) -> None:
        """Append one JSON line to the ledger file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict()) + "\n")

    def _load(self) -> None:
        """Rebuild in-memory pending cache from the JSONL ledger."""
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                seen: dict[str, EscalationEvent] = {}
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        ev = EscalationEvent.from_dict(data)
                        # Later entries overwrite earlier (handles resolution records)
                        seen[ev.event_id] = ev
                    except Exception as exc:
                        logger.warning("EscalationChain: bad ledger line: %s", exc)
            # Only keep unresolved events in the live cache
            self._events = {eid: ev for eid, ev in seen.items() if not ev.resolved}
        except Exception as exc:
            logger.warning("EscalationChain: could not load ledger: %s", exc)
