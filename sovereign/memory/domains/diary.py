"""Memory domain: diary — dated journal entries, moods, reflections."""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/diary.json")
DOMAIN_NAME = "diary"


@dataclass
class DiaryEntry:
    entry_id: str
    date: str                          # ISO date YYYY-MM-DD
    content: str = ""
    mood: str = ""                     # happy | neutral | stressed | anxious | energized
    mood_score: float = 5.0            # 0–10
    energy_level: float = 5.0         # 0–10
    highlights: list[str] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)
    gratitude: list[str] = field(default_factory=list)
    intentions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DiaryMemoryStore:
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
        return {"entries": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, default=str))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_entry(self, entry: DiaryEntry) -> None:
        if not entry.created_at:
            entry.created_at = self._now()
        entry.updated_at = self._now()
        self._data["entries"][entry.entry_id] = entry.to_dict()
        self._save()

    def get_entry(self, entry_id: str) -> DiaryEntry | None:
        raw = self._data["entries"].get(entry_id)
        if raw is None:
            return None
        return DiaryEntry(**{k: v for k, v in raw.items() if k in DiaryEntry.__dataclass_fields__})

    def get_by_date(self, date: str) -> list[DiaryEntry]:
        return [
            DiaryEntry(**{k: v for k, v in e.items() if k in DiaryEntry.__dataclass_fields__})
            for e in self._data["entries"].values()
            if e.get("date") == date
        ]

    def recent(self, n: int = 7) -> list[DiaryEntry]:
        entries = list(self._data["entries"].values())
        entries.sort(key=lambda e: e.get("date", ""), reverse=True)
        return [
            DiaryEntry(**{k: v for k, v in e.items() if k in DiaryEntry.__dataclass_fields__})
            for e in entries[:n]
        ]

    def average_mood(self, days: int = 30) -> float:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        scores = [
            e.get("mood_score", 5.0)
            for e in self._data["entries"].values()
            if e.get("date", "") >= cutoff
        ]
        return sum(scores) / len(scores) if scores else 5.0

    def to_context_string(self) -> str:
        recent = self.recent(3)
        if not recent:
            return "No diary entries."
        lines = [f"{e.date}: mood={e.mood or '?'} score={e.mood_score}" for e in recent]
        return "Recent diary: " + " | ".join(lines)


store = DiaryMemoryStore()
