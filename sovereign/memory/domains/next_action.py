"""Memory domain: next_action — GTD-style next actions per project/area."""
from __future__ import annotations

import json
from sovereign.memory._atomic_io import _save_json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/next_action.json")
DOMAIN_NAME = "next_action"


@dataclass
class NextAction:
    action_id: str
    title: str
    project_id: str = ""              # links to project domain
    context: str = "@anywhere"        # @home | @office | @phone | @computer | @anywhere
    energy_required: str = "medium"   # low | medium | high
    time_estimate_min: int = 30
    priority: str = "medium"          # low | medium | high | critical
    status: str = "pending"           # pending | in_progress | done | deferred | cancelled
    due_date: str = ""
    defer_until: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NextActionStore:
    def __init__(self, data_file: pathlib.Path = _DATA_FILE) -> None:
        self._path = data_file
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        return {"actions": {}}

    def _save(self) -> None:
        _save_json(self._path, self._data)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_action(self, action: NextAction) -> None:
        if not action.created_at:
            action.created_at = self._now()
        self._data["actions"][action.action_id] = action.to_dict()
        self._save()

    def complete_action(self, action_id: str) -> None:
        rec = self._data["actions"].get(action_id)
        if rec:
            rec["status"] = "done"
            rec["completed_at"] = self._now()
            self._save()

    def pending(self) -> list[NextAction]:
        return [
            NextAction(**{k: v for k, v in a.items() if k in NextAction.__dataclass_fields__})
            for a in self._data["actions"].values()
            if a.get("status") == "pending"
        ]

    def by_project(self, project_id: str) -> list[NextAction]:
        return [
            NextAction(**{k: v for k, v in a.items() if k in NextAction.__dataclass_fields__})
            for a in self._data["actions"].values()
            if a.get("project_id") == project_id and a.get("status") == "pending"
        ]

    def urgent(self) -> list[NextAction]:
        return [
            NextAction(**{k: v for k, v in a.items() if k in NextAction.__dataclass_fields__})
            for a in self._data["actions"].values()
            if a.get("priority") in ("high", "critical") and a.get("status") == "pending"
        ]

    def overdue(self) -> list[NextAction]:
        now = self._now()[:10]   # date only
        return [
            NextAction(**{k: v for k, v in a.items() if k in NextAction.__dataclass_fields__})
            for a in self._data["actions"].values()
            if a.get("due_date") and a["due_date"] < now and a.get("status") == "pending"
        ]

    def to_context_string(self) -> str:
        pending = len(self.pending())
        urgent = len(self.urgent())
        overdue = len(self.overdue())
        parts = [f"Next actions: {pending} pending"]
        if urgent:
            parts.append(f"Urgent: {urgent}")
        if overdue:
            parts.append(f"⚠️ Overdue: {overdue}")
        return " | ".join(parts)


store = NextActionStore()
