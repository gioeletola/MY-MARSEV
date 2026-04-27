"""
Change management for SOVEREIGN AI OS.

Provides a structured workflow for proposing, reviewing, deploying, and
rolling back changes to system configuration, agents, policies, and more.

Persists change records to data/ledger/changes.jsonl.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_CHANGES_PATH = Path("data/ledger/changes.jsonl")

# ---------------------------------------------------------------------------
# Enums & Dataclasses
# ---------------------------------------------------------------------------


class ChangeType(str, Enum):
    CONFIG = "config"
    AGENT = "agent"
    WORKFLOW = "workflow"
    POLICY = "policy"
    PROMPT = "prompt"
    MODEL = "model"
    INTEGRATION = "integration"


class ChangeStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPLOYED = "deployed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ChangeRecord:
    """Full lifecycle record for a system change."""

    change_id: str
    change_type: ChangeType
    title: str
    description: str
    proposed_by: str
    status: ChangeStatus
    risk_level: str              # "low" | "medium" | "high" | "critical"
    rollback_plan: str
    approved_by: str = ""
    deployed_at: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "change_type": self.change_type.value,
            "title": self.title,
            "description": self.description,
            "proposed_by": self.proposed_by,
            "status": self.status.value,
            "risk_level": self.risk_level,
            "rollback_plan": self.rollback_plan,
            "approved_by": self.approved_by,
            "deployed_at": self.deployed_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChangeRecord:
        return cls(
            change_id=data["change_id"],
            change_type=ChangeType(data["change_type"]),
            title=data["title"],
            description=data.get("description", ""),
            proposed_by=data["proposed_by"],
            status=ChangeStatus(data["status"]),
            risk_level=data.get("risk_level", "medium"),
            rollback_plan=data.get("rollback_plan", ""),
            approved_by=data.get("approved_by", ""),
            deployed_at=data.get("deployed_at", ""),
            created_at=data.get("created_at", ""),
        )


# ---------------------------------------------------------------------------
# Change Management
# ---------------------------------------------------------------------------


class ChangeManagement:
    """
    Manages the change lifecycle: propose → approve/reject → deploy → rollback.

    All state transitions are appended to the JSONL ledger; the in-memory
    store always reflects the latest status per change_id.

    Usage::

        cm = ChangeManagement()
        record = cm.propose(
            title="Upgrade CEO agent model",
            description="Switch from claude-sonnet-4-6 to claude-opus-4-6",
            change_type=ChangeType.MODEL,
            proposed_by="admin@example.com",
            risk_level="medium",
            rollback_plan="Revert model field in agent spec and restart.",
        )
        cm.approve(record.change_id, approved_by="owner@example.com")
        cm.deploy(record.change_id)
    """

    def __init__(self, persist_path: Path | None = None) -> None:
        self._path: Path = persist_path or _CHANGES_PATH
        # change_id → ChangeRecord (latest state)
        self._records: dict[str, ChangeRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def propose(
        self,
        title: str,
        description: str,
        change_type: ChangeType,
        proposed_by: str,
        risk_level: str,
        rollback_plan: str,
    ) -> ChangeRecord:
        """Create a new change proposal with status PROPOSED."""
        record = ChangeRecord(
            change_id=str(uuid.uuid4()),
            change_type=change_type,
            title=title,
            description=description,
            proposed_by=proposed_by,
            status=ChangeStatus.PROPOSED,
            risk_level=risk_level,
            rollback_plan=rollback_plan,
        )
        self._records[record.change_id] = record
        self._append(record)
        logger.info(
            "ChangeManagement: proposed '%s' [%s] by %s — id=%s",
            title, change_type.value, proposed_by, record.change_id[:8],
        )
        return record

    def approve(self, change_id: str, approved_by: str) -> bool:
        """
        Transition a PROPOSED change to APPROVED.

        Returns True on success, False if the change is not in PROPOSED state
        or does not exist.
        """
        record = self._records.get(change_id)
        if record is None:
            logger.warning("ChangeManagement.approve: unknown change_id '%s'", change_id)
            return False
        if record.status != ChangeStatus.PROPOSED:
            logger.warning(
                "ChangeManagement.approve: change %s is in status '%s', cannot approve",
                change_id[:8], record.status.value,
            )
            return False
        record.status = ChangeStatus.APPROVED
        record.approved_by = approved_by
        self._append(record)
        logger.info("ChangeManagement: approved change %s by %s", change_id[:8], approved_by)
        return True

    def reject(self, change_id: str, reason: str) -> bool:
        """
        Transition a PROPOSED change to REJECTED.

        Returns True on success, False otherwise.
        """
        record = self._records.get(change_id)
        if record is None:
            logger.warning("ChangeManagement.reject: unknown change_id '%s'", change_id)
            return False
        if record.status != ChangeStatus.PROPOSED:
            logger.warning(
                "ChangeManagement.reject: change %s is in status '%s', cannot reject",
                change_id[:8], record.status.value,
            )
            return False
        record.status = ChangeStatus.REJECTED
        # Store rejection reason in description suffix
        record.description = f"{record.description}\n[REJECTED] {reason}".strip()
        self._append(record)
        logger.info("ChangeManagement: rejected change %s — %s", change_id[:8], reason)
        return True

    def deploy(self, change_id: str) -> bool:
        """
        Transition an APPROVED change to DEPLOYED.

        Returns True on success, False if not APPROVED.
        """
        record = self._records.get(change_id)
        if record is None:
            logger.warning("ChangeManagement.deploy: unknown change_id '%s'", change_id)
            return False
        if record.status != ChangeStatus.APPROVED:
            logger.warning(
                "ChangeManagement.deploy: change %s is in status '%s', cannot deploy",
                change_id[:8], record.status.value,
            )
            return False
        record.status = ChangeStatus.DEPLOYED
        record.deployed_at = datetime.now(timezone.utc).isoformat()
        self._append(record)
        logger.info(
            "ChangeManagement: deployed change %s at %s",
            change_id[:8], record.deployed_at,
        )
        return True

    def rollback(self, change_id: str) -> bool:
        """
        Transition a DEPLOYED change to ROLLED_BACK.

        Returns True on success, False if not DEPLOYED.
        """
        record = self._records.get(change_id)
        if record is None:
            logger.warning("ChangeManagement.rollback: unknown change_id '%s'", change_id)
            return False
        if record.status != ChangeStatus.DEPLOYED:
            logger.warning(
                "ChangeManagement.rollback: change %s is in status '%s', cannot roll back",
                change_id[:8], record.status.value,
            )
            return False
        record.status = ChangeStatus.ROLLED_BACK
        self._append(record)
        logger.info("ChangeManagement: rolled back change %s", change_id[:8])
        return True

    def pending(self) -> list[ChangeRecord]:
        """Return all changes in PROPOSED or APPROVED state, sorted oldest-first."""
        return sorted(
            (r for r in self._records.values()
             if r.status in (ChangeStatus.PROPOSED, ChangeStatus.APPROVED)),
            key=lambda r: r.created_at,
        )

    def get(self, change_id: str) -> ChangeRecord | None:
        """Look up a change record by ID."""
        return self._records.get(change_id)

    def all_records(self) -> list[ChangeRecord]:
        """Return all known change records, newest-first."""
        return sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _append(self, record: ChangeRecord) -> None:
        """Append the current state of a record as a new JSONL line."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict()) + "\n")

    def _load(self) -> None:
        """Replay the JSONL ledger; later entries overwrite earlier ones."""
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        record = ChangeRecord.from_dict(data)
                        self._records[record.change_id] = record
                    except Exception as exc:
                        logger.warning("ChangeManagement: bad ledger line: %s", exc)
        except Exception as exc:
            logger.warning("ChangeManagement: could not load ledger: %s", exc)
