"""Memory domain: operational — SOPs, workflows, processes, checklists, runbooks."""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/operational.json")
DOMAIN_NAME = "operational"


@dataclass
class SOP:
    sop_id: str
    title: str
    category: str = "general"         # onboarding | finance | security | hr | ops | tech | marketing
    version: str = "1.0"
    status: str = "active"            # draft | active | deprecated
    owner: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)   # [{step, description, duration_min}]
    prerequisites: list[str] = field(default_factory=list)
    tools_required: list[str] = field(default_factory=list)
    frequency: str = ""               # daily | weekly | monthly | ad-hoc | triggered
    estimated_duration_min: int = 0
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Checklist:
    checklist_id: str
    title: str
    items: list[dict[str, Any]] = field(default_factory=list)   # [{item, done, notes}]
    context: str = ""
    completed: bool = False
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OperationalMemoryStore:
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
        return {"sops": {}, "checklists": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, default=str))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_sop(self, sop: SOP) -> None:
        if not sop.created_at:
            sop.created_at = self._now()
        sop.updated_at = self._now()
        self._data["sops"][sop.sop_id] = sop.to_dict()
        self._save()

    def get_sop(self, sop_id: str) -> SOP | None:
        raw = self._data["sops"].get(sop_id)
        if raw is None:
            return None
        return SOP(**{k: v for k, v in raw.items() if k in SOP.__dataclass_fields__})

    def active_sops(self, category: str | None = None) -> list[SOP]:
        sops = [
            SOP(**{k: v for k, v in s.items() if k in SOP.__dataclass_fields__})
            for s in self._data["sops"].values()
            if s.get("status") == "active"
        ]
        if category:
            sops = [s for s in sops if s.category == category]
        return sops

    def add_checklist(self, checklist: Checklist) -> None:
        if not checklist.created_at:
            checklist.created_at = self._now()
        self._data["checklists"][checklist.checklist_id] = checklist.to_dict()
        self._save()

    def complete_checklist(self, checklist_id: str) -> None:
        cl = self._data["checklists"].get(checklist_id)
        if cl:
            cl["completed"] = True
            cl["completed_at"] = self._now()
            self._save()

    def to_context_string(self) -> str:
        sop_count = len([s for s in self._data["sops"].values() if s.get("status") == "active"])
        open_cls = len([c for c in self._data["checklists"].values() if not c.get("completed")])
        parts = [f"Active SOPs: {sop_count}"]
        if open_cls:
            parts.append(f"Open checklists: {open_cls}")
        return " | ".join(parts)


store = OperationalMemoryStore()
