"""Memory domain: personal_constitution — core principles, values, red lines, and identity."""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/personal_constitution.json")
DOMAIN_NAME = "personal_constitution"


@dataclass
class PersonalConstitution:
    core_values: list[str] = field(default_factory=list)
    life_principles: list[str] = field(default_factory=list)
    non_negotiables: list[str] = field(default_factory=list)     # absolute red lines
    goals_2026: list[str] = field(default_factory=list)
    economic_goals_2026: list[str] = field(default_factory=list)
    glow_up_goals: list[str] = field(default_factory=list)        # physique, style, presence
    personal_mission: str = ""
    personal_vision: str = ""
    fears_to_overcome: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    mistakes_to_not_repeat: list[str] = field(default_factory=list)
    role_models: list[str] = field(default_factory=list)
    daily_non_negotiables: list[str] = field(default_factory=list)  # daily musts
    version: str = "1.0"
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RedFlag:
    flag_id: str
    title: str
    description: str = ""
    category: str = "behavior"          # behavior | financial | relationship | health | work
    severity: str = "medium"            # low | medium | high | critical
    triggers: list[str] = field(default_factory=list)
    response_plan: str = ""
    active: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PersonalConstitutionStore:
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
        return {"constitution": {}, "red_flags": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, default=str))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_constitution(self) -> PersonalConstitution:
        return PersonalConstitution(**{
            k: v for k, v in self._data.get("constitution", {}).items()
            if k in PersonalConstitution.__dataclass_fields__
        })

    def update_constitution(self, **kwargs: Any) -> None:
        rec = self._data.setdefault("constitution", {})
        rec.update(kwargs)
        rec["last_updated"] = self._now()
        self._save()

    def add_red_flag(self, flag: RedFlag) -> None:
        if not flag.created_at:
            flag.created_at = self._now()
        self._data.setdefault("red_flags", {})[flag.flag_id] = flag.to_dict()
        self._save()

    def active_red_flags(self) -> list[RedFlag]:
        return [
            RedFlag(**{k: v for k, v in f.items() if k in RedFlag.__dataclass_fields__})
            for f in self._data.get("red_flags", {}).values()
            if f.get("active", True)
        ]

    def red_flags_by_severity(self, severity: str) -> list[RedFlag]:
        return [f for f in self.active_red_flags() if f.severity == severity]

    def to_context_string(self) -> str:
        c = self.get_constitution()
        parts = []
        if c.personal_mission:
            parts.append(f"Mission: {c.personal_mission}")
        if c.core_values:
            parts.append(f"Values: {', '.join(c.core_values[:5])}")
        if c.goals_2026:
            parts.append(f"Goals 2026: {', '.join(c.goals_2026[:3])}")
        critical = self.red_flags_by_severity("critical")
        if critical:
            parts.append(f"⚠️ Critical flags: {len(critical)}")
        return " | ".join(parts) if parts else "Constitution not configured."


store = PersonalConstitutionStore()
