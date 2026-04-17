"""
Agent Quarantine Mode — isolate misbehaving agents from the SOVEREIGN AI OS.

Quarantine state is persisted to data/memory/quarantine.json.  An agent
under quarantine should be refused task allocation by the scheduler; this
module only manages the registry of quarantined agents.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_QUARANTINE_PATH = Path("data/memory/quarantine.json")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class QuarantineRecord:
    """Immutable-ish record describing a quarantine event for an agent."""

    agent_id: str
    reason: str
    quarantined_at: str
    released_at: str = ""
    quarantined_by: str = "system"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> QuarantineRecord:
        return QuarantineRecord(**d)

    @property
    def is_active(self) -> bool:
        """*True* if the quarantine has not been lifted."""
        return self.released_at == ""


# ---------------------------------------------------------------------------
# Quarantine Manager
# ---------------------------------------------------------------------------


class QuarantineManager:
    """Registry of agents currently (or previously) under quarantine.

    Only active quarantines are returned by :meth:`quarantined_agents`.
    Historical records are retained in the store for audit purposes.
    """

    def __init__(self, store_path: Path = _QUARANTINE_PATH) -> None:
        self._path = store_path
        # agent_id -> most-recent QuarantineRecord (may be released)
        self._records: dict[str, QuarantineRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def quarantine(
        self,
        agent_id: str,
        reason: str,
        quarantined_by: str = "system",
    ) -> QuarantineRecord:
        """Place *agent_id* under quarantine.

        If the agent is already quarantined the existing record is returned
        unchanged (call :meth:`release` first to re-quarantine with a new
        reason).
        """
        existing = self._records.get(agent_id)
        if existing and existing.is_active:
            logger.info(
                "Agent already quarantined: agent_id=%s reason=%s",
                agent_id,
                existing.reason,
            )
            return existing

        record = QuarantineRecord(
            agent_id=agent_id,
            reason=reason,
            quarantined_at=datetime.now(timezone.utc).isoformat(),
            quarantined_by=quarantined_by,
        )
        self._records[agent_id] = record
        self._save()
        logger.warning(
            "Agent quarantined: agent_id=%s reason=%s by=%s",
            agent_id,
            reason,
            quarantined_by,
        )
        return record

    def release(self, agent_id: str, released_by: str = "system") -> bool:
        """Lift the quarantine for *agent_id*.

        Returns *True* if the agent was actively quarantined and has now been
        released; *False* if the agent was not quarantined.
        """
        record = self._records.get(agent_id)
        if record is None or not record.is_active:
            logger.info("Release no-op — agent not quarantined: agent_id=%s", agent_id)
            return False
        record.released_at = datetime.now(timezone.utc).isoformat()
        self._save()
        logger.info(
            "Agent released from quarantine: agent_id=%s by=%s", agent_id, released_by
        )
        return True

    def is_quarantined(self, agent_id: str) -> bool:
        """Return *True* if *agent_id* is currently under active quarantine."""
        record = self._records.get(agent_id)
        return record is not None and record.is_active

    def quarantined_agents(self) -> list[QuarantineRecord]:
        """Return all *active* quarantine records."""
        return [r for r in self._records.values() if r.is_active]

    def check_and_quarantine(
        self,
        agent_id: str,
        failure_count: int,
        threshold: int = 5,
    ) -> bool:
        """Auto-quarantine *agent_id* if *failure_count* >= *threshold*.

        Returns *True* if a quarantine was triggered (or was already active),
        *False* if the threshold was not reached.
        """
        if failure_count < threshold:
            return False
        if not self.is_quarantined(agent_id):
            self.quarantine(
                agent_id=agent_id,
                reason=f"Auto-quarantine: failure_count={failure_count} >= threshold={threshold}",
                quarantined_by="system",
            )
        return True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._records = {k: QuarantineRecord.from_dict(v) for k, v in data.items()}
        except Exception:
            logger.exception("Failed to load quarantine store; starting empty")

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {aid: r.to_dict() for aid, r in self._records.items()}
        self._path.write_text(json.dumps(payload, indent=2))
