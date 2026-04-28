"""Memory domain: decision — logged decisions, rationale, outcomes, reviews."""
from __future__ import annotations

import json
from sovereign.memory._atomic_io import _save_json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/decision.json")
DOMAIN_NAME = "decision"


@dataclass
class DecisionRecord:
    decision_id: str
    title: str
    description: str = ""
    domain: str = "general"              # business | personal | financial | strategic | operational
    status: str = "open"                 # open | decided | implemented | reviewed | reversed
    options_considered: list[str] = field(default_factory=list)
    chosen_option: str = ""
    rationale: str = ""
    risks: list[str] = field(default_factory=list)
    expected_outcome: str = ""
    actual_outcome: str = ""
    confidence: float = 0.7              # 0–1
    reversible: bool = True
    stakeholders: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    decided_at: str = ""
    review_at: str = ""                  # ISO datetime for scheduled review
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DecisionMemoryStore:
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
        return {"decisions": {}}

    def _save(self) -> None:
        _save_json(self._path, self._data)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_decision(self, rec: DecisionRecord) -> None:
        if not rec.created_at:
            rec.created_at = self._now()
        rec.updated_at = self._now()
        self._data["decisions"][rec.decision_id] = rec.to_dict()
        self._save()

    def update_decision(self, decision_id: str, **kwargs: Any) -> None:
        rec = self._data["decisions"].get(decision_id)
        if rec:
            rec.update(kwargs)
            rec["updated_at"] = self._now()
            self._save()

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        raw = self._data["decisions"].get(decision_id)
        if raw is None:
            return None
        return DecisionRecord(**{k: v for k, v in raw.items() if k in DecisionRecord.__dataclass_fields__})

    def by_status(self, status: str) -> list[DecisionRecord]:
        return [
            DecisionRecord(**{k: v for k, v in d.items() if k in DecisionRecord.__dataclass_fields__})
            for d in self._data["decisions"].values()
            if d.get("status") == status
        ]

    def pending_review(self) -> list[DecisionRecord]:
        now = self._now()
        return [
            DecisionRecord(**{k: v for k, v in d.items() if k in DecisionRecord.__dataclass_fields__})
            for d in self._data["decisions"].values()
            if d.get("review_at") and d["review_at"] <= now
        ]

    def to_context_string(self) -> str:
        open_decisions = self.by_status("open")
        if not open_decisions:
            return "No open decisions."
        titles = [d.title for d in open_decisions[:3]]
        return f"Open decisions ({len(open_decisions)}): {', '.join(titles)}"


store = DecisionMemoryStore()
