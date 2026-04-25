"""Memory domain: business_idea — structured idea archive with scoring and validation status."""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/business_idea.json")
DOMAIN_NAME = "business_idea"


@dataclass
class BusinessIdea:
    idea_id: str
    name: str
    description: str = ""
    budget_needed: float = 0.0
    currency: str = "EUR"
    potential_monthly_revenue: float = 0.0
    difficulty: str = "medium"            # easy | medium | hard | very_hard
    time_to_launch_months: int = 6
    people_needed: int = 1
    first_step: str = ""
    score: int = 5                        # 1–10 subjective score
    status: str = "idea"                  # idea | validation | active | frozen | discarded
    market_size: str = ""
    competition_level: str = "medium"     # low | medium | high
    unique_value_proposition: str = ""
    risks: list[str] = field(default_factory=list)
    resources_needed: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BusinessIdeaMemoryStore:
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
        return {"ideas": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, default=str))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_idea(self, idea: BusinessIdea) -> None:
        if not idea.created_at:
            idea.created_at = self._now()
        idea.updated_at = self._now()
        self._data["ideas"][idea.idea_id] = idea.to_dict()
        self._save()

    def update_idea(self, idea_id: str, **kwargs: Any) -> None:
        rec = self._data["ideas"].get(idea_id)
        if rec:
            rec.update(kwargs)
            rec["updated_at"] = self._now()
            self._save()

    def get_idea(self, idea_id: str) -> BusinessIdea | None:
        raw = self._data["ideas"].get(idea_id)
        if raw is None:
            return None
        return BusinessIdea(**{k: v for k, v in raw.items() if k in BusinessIdea.__dataclass_fields__})

    def by_status(self, status: str) -> list[BusinessIdea]:
        return [
            BusinessIdea(**{k: v for k, v in i.items() if k in BusinessIdea.__dataclass_fields__})
            for i in self._data["ideas"].values()
            if i.get("status") == status
        ]

    def top_scored(self, n: int = 5) -> list[BusinessIdea]:
        ideas = [
            BusinessIdea(**{k: v for k, v in i.items() if k in BusinessIdea.__dataclass_fields__})
            for i in self._data["ideas"].values()
            if i.get("status") not in ("discarded",)
        ]
        ideas.sort(key=lambda x: x.score, reverse=True)
        return ideas[:n]

    def to_context_string(self) -> str:
        active = self.by_status("active")
        validation = self.by_status("validation")
        top = self.top_scored(3)
        parts = [f"Business ideas: {len(self._data['ideas'])} total"]
        if active:
            parts.append(f"Active: {', '.join(i.name for i in active)}")
        if validation:
            parts.append(f"Validating: {', '.join(i.name for i in validation)}")
        if top:
            parts.append(f"Top ideas: {', '.join(f'{i.name}({i.score}/10)' for i in top[:3])}")
        return " | ".join(parts)


store = BusinessIdeaMemoryStore()
