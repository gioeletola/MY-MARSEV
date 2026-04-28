"""Memory domain: personal_version — monthly snapshots of 'version of yourself'."""
from __future__ import annotations

import json
from sovereign.memory._atomic_io import _save_json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/personal_version.json")
DOMAIN_NAME = "personal_version"


@dataclass
class PersonalVersion:
    version_id: str
    period: str                            # e.g. "2026-04" (YYYY-MM)
    version_label: str = ""               # e.g. "v2.4 — The Builder"

    # Physical
    weight_kg: float = 0.0
    body_fat_pct: float = 0.0
    fitness_level: str = ""
    physique_rating: int = 5              # 1–10 self-rating

    # Mental / emotional
    stress_level: str = "medium"
    clarity_level: str = "medium"
    energy_level: str = "medium"
    mental_health_notes: str = ""

    # Financial
    net_worth: float = 0.0
    monthly_income: float = 0.0
    monthly_expenses: float = 0.0
    savings_rate_pct: float = 0.0

    # Skills / growth
    top_skills: list[str] = field(default_factory=list)
    learning_this_month: list[str] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)

    # Social
    key_relationships: list[str] = field(default_factory=list)
    network_score: int = 5               # 1–10

    # Projects / work
    active_projects: list[str] = field(default_factory=list)
    completed_projects: list[str] = field(default_factory=list)
    work_satisfaction: int = 5           # 1–10

    # Reflection
    month_summary: str = ""
    next_month_focus: str = ""
    overall_rating: int = 5             # 1–10 "how good was this month"

    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PersonalVersionStore:
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
        return {"versions": {}}

    def _save(self) -> None:
        _save_json(self._path, self._data)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def save_version(self, version: PersonalVersion) -> None:
        if not version.created_at:
            version.created_at = self._now()
        self._data["versions"][version.version_id] = version.to_dict()
        self._save()

    def get_version(self, version_id: str) -> PersonalVersion | None:
        raw = self._data["versions"].get(version_id)
        if raw is None:
            return None
        return PersonalVersion(**{k: v for k, v in raw.items() if k in PersonalVersion.__dataclass_fields__})

    def latest(self) -> PersonalVersion | None:
        versions = list(self._data["versions"].values())
        if not versions:
            return None
        versions.sort(key=lambda v: v.get("period", ""), reverse=True)
        raw = versions[0]
        return PersonalVersion(**{k: v for k, v in raw.items() if k in PersonalVersion.__dataclass_fields__})

    def history(self, n: int = 12) -> list[PersonalVersion]:
        versions = list(self._data["versions"].values())
        versions.sort(key=lambda v: v.get("period", ""), reverse=True)
        return [
            PersonalVersion(**{k: v for k, v in ver.items() if k in PersonalVersion.__dataclass_fields__})
            for ver in versions[:n]
        ]

    def trend_net_worth(self) -> list[dict[str, Any]]:
        return [
            {"period": v.get("period"), "net_worth": v.get("net_worth", 0.0)}
            for v in sorted(self._data["versions"].values(), key=lambda x: x.get("period", ""))
        ]

    def to_context_string(self) -> str:
        latest = self.latest()
        if not latest:
            return "No personal versions recorded."
        return (
            f"Latest version ({latest.period}): "
            f"net_worth={latest.net_worth:.0f} | "
            f"income={latest.monthly_income:.0f}/mo | "
            f"rating={latest.overall_rating}/10"
        )


store = PersonalVersionStore()
