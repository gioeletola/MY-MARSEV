"""
Session Monitor — records, tracks, and analyses agent session activity.

Events are appended to a JSONL ledger for persistence.  Anomaly detection
uses two heuristics:
  * Rate spike  — more than 20 events per minute within a single session.
  * Unknown agent — agent_id does not start with a recognised prefix.

Recognised agent prefixes are drawn from the SOVEREIGN_AGENT_PREFIXES
environment variable (comma-separated) or the built-in default list.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Deque

logger = logging.getLogger(__name__)

_LEDGER_PATH = Path("data/ledger/sessions.jsonl")
_RATE_WINDOW_SECONDS = 60
_RATE_THRESHOLD = 20  # events per window

_DEFAULT_AGENT_PREFIXES = (
    "agent-",
    "sovereign-",
    "sys-",
    "kernel-",
    "swarm-",
    "user-",
)


def _known_prefixes() -> tuple[str, ...]:
    env = os.environ.get("SOVEREIGN_AGENT_PREFIXES", "")
    if env:
        return tuple(p.strip() for p in env.split(",") if p.strip())
    return _DEFAULT_AGENT_PREFIXES


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SessionEvent:
    """A single recorded event within a session."""

    event_id: str
    session_id: str
    event_type: str
    agent_id: str
    details: dict
    ts: float
    anomaly: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> SessionEvent:
        return SessionEvent(**d)


# ---------------------------------------------------------------------------
# Session Monitor
# ---------------------------------------------------------------------------


class SessionMonitor:
    """Track session events and flag anomalies.

    In-memory state is the primary store; events are also appended to a
    JSONL file for durability.
    """

    def __init__(self, ledger_path: Path = _LEDGER_PATH) -> None:
        self._path = ledger_path
        # session_id -> ordered list of events
        self._sessions: dict[str, list[SessionEvent]] = defaultdict(list)
        # session_id -> closed flag
        self._closed: set[str] = set()
        # anomaly list (references into _sessions entries)
        self._anomalies: list[SessionEvent] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        session_id: str,
        event_type: str,
        agent_id: str,
        details: dict | None = None,
    ) -> SessionEvent:
        """Append a new event to *session_id* and check for anomalies."""
        if details is None:
            details = {}
        event = SessionEvent(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            event_type=event_type,
            agent_id=agent_id,
            details=details,
            ts=time.time(),
        )
        event.anomaly = self._detect_anomaly(event)
        self._sessions[session_id].append(event)
        if event.anomaly:
            self._anomalies.append(event)
            logger.warning(
                "Session anomaly detected: session=%s agent=%s type=%s",
                session_id,
                agent_id,
                event_type,
            )
        self._append_ledger(event)
        return event

    def get_session(self, session_id: str) -> list[SessionEvent]:
        """Return all events recorded for *session_id*."""
        return list(self._sessions.get(session_id, []))

    def active_sessions(self) -> list[str]:
        """Return IDs of sessions that have not been explicitly closed."""
        return [sid for sid in self._sessions if sid not in self._closed]

    def close_session(self, session_id: str) -> None:
        """Mark a session as closed."""
        self._closed.add(session_id)
        logger.info("Session closed: session_id=%s", session_id)

    def anomalies(self) -> list[SessionEvent]:
        """Return all events that were flagged as anomalous."""
        return list(self._anomalies)

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    def _detect_anomaly(self, event: SessionEvent) -> bool:
        """Return *True* if *event* should be considered suspicious.

        Checks:
        1. Rate spike: the session already has ≥ *_RATE_THRESHOLD* events
           in the last *_RATE_WINDOW_SECONDS*.
        2. Unknown agent: *agent_id* does not start with any recognised prefix.
        """
        # --- Check 1: rate spike ----------------------------------------
        recent = self._sessions.get(event.session_id, [])
        cutoff = event.ts - _RATE_WINDOW_SECONDS
        recent_count = sum(1 for e in recent if e.ts >= cutoff)
        if recent_count >= _RATE_THRESHOLD:
            return True

        # --- Check 2: unknown agent prefix --------------------------------
        prefixes = _known_prefixes()
        if not any(event.agent_id.startswith(p) for p in prefixes):
            return True

        return False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _append_ledger(self, event: SessionEvent) -> None:
        """Append a single JSON line to the ledger file."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")
        except Exception:
            logger.exception("Failed to append session event to ledger")

    def _load(self) -> None:
        """Replay the ledger file into in-memory state on startup."""
        if not self._path.exists():
            return
        try:
            with self._path.open() as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        event = SessionEvent.from_dict(d)
                        self._sessions[event.session_id].append(event)
                        if event.anomaly:
                            self._anomalies.append(event)
                    except Exception:
                        logger.warning("Skipping malformed ledger line: %r", line[:80])
        except Exception:
            logger.exception("Failed to load session ledger; starting empty")
