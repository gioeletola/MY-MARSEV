"""
Decision ledger — append-only audit log of significant system decisions.

Every major decision (task dispatch, approval, mode change, tool execution,
escalation) is recorded here. The ledger is immutable: records are only
appended, never modified or deleted.

Persisted as JSONL to data/ledger/decisions.jsonl.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionRecord:
    """Immutable record of a significant decision made by the system."""

    session_id: str
    agent_id: str
    decision_type: str          # "task_dispatch" | "approval" | "mode_change" | "tool_exec" | ...
    description: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    confidence: float = 0.0
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "decision_type": self.decision_type,
            "description": self.description,
            "inputs": self.inputs,
            "outcome": self.outcome,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


class DecisionLedger:
    """
    Append-only decision ledger.

    Thread-safe for async single-process use. For multi-process deployments,
    replace with a database-backed implementation.
    """

    def __init__(self, data_dir: str | pathlib.Path = "data") -> None:
        ledger_dir = pathlib.Path(data_dir) / "ledger"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        self._path = ledger_dir / "decisions.jsonl"

    async def record(self, decision: DecisionRecord) -> None:
        """Append a decision record to the ledger. Never overwrites existing records."""
        line = json.dumps(decision.to_dict(), ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    async def query(
        self,
        session_id: str | None = None,
        agent_id: str | None = None,
        decision_type: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[DecisionRecord]:
        """
        Filter and return decision records.

        All filters are optional and ANDed together.
        Returns records in chronological order (oldest first).
        """
        if not self._path.exists():
            return []

        records: list[DecisionRecord] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if session_id and data.get("session_id") != session_id:
                    continue
                if agent_id and data.get("agent_id") != agent_id:
                    continue
                if decision_type and data.get("decision_type") != decision_type:
                    continue
                if since and data.get("timestamp", "") < since:
                    continue

                records.append(
                    DecisionRecord(
                        session_id=data["session_id"],
                        agent_id=data["agent_id"],
                        decision_type=data["decision_type"],
                        description=data["description"],
                        inputs=data.get("inputs", {}),
                        outcome=data.get("outcome", ""),
                        confidence=data.get("confidence", 0.0),
                        decision_id=data["decision_id"],
                        timestamp=data["timestamp"],
                    )
                )

        return records[-limit:]

    async def count(self) -> int:
        """Return total number of records in the ledger."""
        if not self._path.exists():
            return 0
        count = 0
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count
