"""
Incident Registry — append-only log of system incidents, errors, and anomalies.

Used by the self-healer and observability layer.
"""
from __future__ import annotations
import json
import logging
import pathlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/ledger/incidents.jsonl")


@dataclass
class Incident:
    """One recorded incident."""
    incident_id: str
    severity: str           # "low" | "medium" | "high" | "critical"
    category: str           # "agent_failure" | "tool_error" | "memory_corruption" | "security" | "other"
    title: str
    description: str
    agent_id: str = ""
    session_id: str = ""
    resolved: bool = False
    resolution_notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str = ""
    tags: list[str] = field(default_factory=list)


class IncidentRegistry:
    """
    Append-only incident log with severity tracking and resolution management.

    Incidents are persisted to JSONL for audit trail.
    """

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._incidents: list[Incident] = []
        self._load()

    # ------------------------------------------------------------------

    def record(self, incident: Incident) -> None:
        """Append an incident to the log."""
        self._incidents.append(incident)
        self._append(incident)
        logger.warning(
            "Incident recorded: [%s] %s (id=%s)",
            incident.severity.upper(), incident.title, incident.incident_id
        )

    def resolve(self, incident_id: str, notes: str = "") -> bool:
        for inc in self._incidents:
            if inc.incident_id == incident_id and not inc.resolved:
                inc.resolved = True
                inc.resolution_notes = notes
                inc.resolved_at = datetime.now(timezone.utc).isoformat()
                self._rewrite()
                logger.info("Incident resolved: %s", incident_id)
                return True
        return False

    def open_incidents(self, severity: str | None = None) -> list[Incident]:
        result = [i for i in self._incidents if not i.resolved]
        if severity:
            result = [i for i in result if i.severity == severity]
        return result

    def by_agent(self, agent_id: str) -> list[Incident]:
        return [i for i in self._incidents if i.agent_id == agent_id]

    def by_category(self, category: str) -> list[Incident]:
        return [i for i in self._incidents if i.category == category]

    def recent(self, limit: int = 20) -> list[Incident]:
        return self._incidents[-limit:]

    def stats(self) -> dict[str, Any]:
        total = len(self._incidents)
        open_ = sum(1 for i in self._incidents if not i.resolved)
        by_sev: dict[str, int] = {}
        for i in self._incidents:
            by_sev[i.severity] = by_sev.get(i.severity, 0) + 1
        return {
            "total": total,
            "open": open_,
            "resolved": total - open_,
            "by_severity": by_sev,
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
                        self._incidents.append(Incident(**json.loads(line)))
            logger.info("IncidentRegistry loaded %d incidents", len(self._incidents))
        except Exception as exc:
            logger.warning("IncidentRegistry load error: %s", exc)

    def _append(self, incident: Incident) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(incident), default=str) + "\n")
        except Exception as exc:
            logger.error("IncidentRegistry append failed: %s", exc)

    def _rewrite(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as f:
                for inc in self._incidents:
                    f.write(json.dumps(asdict(inc), default=str) + "\n")
        except Exception as exc:
            logger.error("IncidentRegistry rewrite failed: %s", exc)
