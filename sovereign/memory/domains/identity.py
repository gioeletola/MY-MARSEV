"""Memory domain: identity — who the user is, preferences, context, persona."""
from __future__ import annotations

import json
from sovereign.memory._atomic_io import _save_json
import logging
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
_DATA_FILE = pathlib.Path("data/memory/identity.json")
DOMAIN_NAME = "identity"


@dataclass
class IdentityRecord:
    """Core identity and persona attributes."""
    full_name: str = ""
    preferred_name: str = ""
    locale: str = "en"
    timezone: str = "UTC"
    operating_mode: str = "command"
    communication_style: str = "direct"   # direct | diplomatic | casual | formal
    risk_tolerance: str = "moderate"      # conservative | moderate | aggressive
    primary_goals: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PreferenceRecord:
    key: str
    value: Any
    category: str = "general"   # ui | behavior | notification | privacy
    updated_at: str = ""


class IdentityMemoryStore:
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
        return {"identity": {}, "preferences": {}}

    def _save(self) -> None:
        _save_json(self._path, self._data)

    def get_identity(self) -> IdentityRecord:
        return IdentityRecord(**{
            k: v for k, v in self._data.get("identity", {}).items()
            if k in IdentityRecord.__dataclass_fields__
        })

    def update_identity(self, **kwargs: Any) -> None:
        rec = self._data.setdefault("identity", {})
        rec.update(kwargs)
        self._save()

    def set_preference(self, key: str, value: Any, category: str = "general") -> None:
        from datetime import datetime, timezone
        self._data.setdefault("preferences", {})[key] = {
            "value": value, "category": category,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def get_preference(self, key: str, default: Any = None) -> Any:
        entry = self._data.get("preferences", {}).get(key)
        return entry["value"] if entry else default

    def all_preferences(self) -> dict[str, Any]:
        return {k: v["value"] for k, v in self._data.get("preferences", {}).items()}

    def to_context_string(self) -> str:
        rec = self.get_identity()
        parts = []
        if rec.full_name:
            parts.append(f"Name: {rec.full_name}")
        if rec.primary_goals:
            parts.append(f"Goals: {', '.join(rec.primary_goals)}")
        if rec.values:
            parts.append(f"Values: {', '.join(rec.values)}")
        if rec.communication_style:
            parts.append(f"Style: {rec.communication_style}")
        return " | ".join(parts) if parts else "Identity not configured."


store = IdentityMemoryStore()
