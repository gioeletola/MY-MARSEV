"""Memory domain: learning — courses, books, skills, notes, progress tracking."""
from __future__ import annotations

import json
from sovereign.memory._atomic_io import _save_json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/learning.json")
DOMAIN_NAME = "learning"


@dataclass
class LearningItem:
    item_id: str
    title: str
    item_type: str = "course"          # course | book | article | video | podcast | tutorial
    status: str = "to_learn"           # to_learn | in_progress | completed | abandoned
    subject: str = ""
    source: str = ""
    url: str = ""
    progress_pct: float = 0.0          # 0–100
    rating: float = 0.0                # 0–5
    notes: str = ""
    key_takeaways: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SkillProgress:
    skill_id: str
    skill_name: str
    level: str = "beginner"            # beginner | intermediate | advanced | expert
    score: float = 0.0                 # 0–100
    evidence: list[str] = field(default_factory=list)
    last_practiced: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LearningMemoryStore:
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
        return {"items": {}, "skills": {}}

    def _save(self) -> None:
        _save_json(self._path, self._data)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_item(self, item: LearningItem) -> None:
        if not item.created_at:
            item.created_at = self._now()
        self._data["items"][item.item_id] = item.to_dict()
        self._save()

    def update_progress(self, item_id: str, progress_pct: float) -> None:
        item = self._data["items"].get(item_id)
        if item:
            item["progress_pct"] = progress_pct
            if progress_pct >= 100.0 and not item.get("completed_at"):
                item["completed_at"] = self._now()
                item["status"] = "completed"
            self._save()

    def by_status(self, status: str) -> list[LearningItem]:
        return [
            LearningItem(**{k: v for k, v in i.items() if k in LearningItem.__dataclass_fields__})
            for i in self._data["items"].values()
            if i.get("status") == status
        ]

    def update_skill(self, skill: SkillProgress) -> None:
        skill.updated_at = self._now()
        self._data.setdefault("skills", {})[skill.skill_id] = skill.to_dict()
        self._save()

    def get_skill(self, skill_id: str) -> SkillProgress | None:
        raw = self._data.get("skills", {}).get(skill_id)
        if raw is None:
            return None
        return SkillProgress(**{k: v for k, v in raw.items() if k in SkillProgress.__dataclass_fields__})

    def all_skills(self) -> list[SkillProgress]:
        return [
            SkillProgress(**{k: v for k, v in s.items() if k in SkillProgress.__dataclass_fields__})
            for s in self._data.get("skills", {}).values()
        ]

    def to_context_string(self) -> str:
        in_progress = self.by_status("in_progress")
        skills = self.all_skills()
        parts = []
        if in_progress:
            parts.append(f"Learning: {', '.join(i.title for i in in_progress[:3])}")
        if skills:
            expert = [s.skill_name for s in skills if s.level in ("advanced", "expert")]
            if expert:
                parts.append(f"Expert skills: {', '.join(expert[:5])}")
        return " | ".join(parts) if parts else "No learning records."


store = LearningMemoryStore()
