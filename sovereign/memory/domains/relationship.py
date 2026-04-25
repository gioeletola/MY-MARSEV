"""Memory domain: relationship — contacts, interactions, relationship health, CRM-lite."""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/relationship.json")
DOMAIN_NAME = "relationship"


@dataclass
class Contact:
    contact_id: str
    full_name: str
    relationship_type: str = "professional"  # professional | personal | family | mentor | partner | client
    email: str = ""
    phone: str = ""
    company: str = ""
    role: str = ""
    location: str = ""
    linkedin: str = ""
    twitter: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    birthday: str = ""
    last_contact: str = ""
    contact_frequency: str = "monthly"   # weekly | monthly | quarterly | yearly
    relationship_score: float = 5.0      # 0–10
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Interaction:
    interaction_id: str
    contact_id: str
    interaction_type: str = "message"    # message | call | meeting | email | social | event
    summary: str = ""
    sentiment: str = "neutral"           # positive | neutral | negative
    follow_up_needed: bool = False
    follow_up_by: str = ""
    occurred_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RelationshipMemoryStore:
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
        return {"contacts": {}, "interactions": []}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, default=str))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_contact(self, contact: Contact) -> None:
        if not contact.created_at:
            contact.created_at = self._now()
        contact.updated_at = self._now()
        self._data["contacts"][contact.contact_id] = contact.to_dict()
        self._save()

    def get_contact(self, contact_id: str) -> Contact | None:
        raw = self._data["contacts"].get(contact_id)
        if raw is None:
            return None
        return Contact(**{k: v for k, v in raw.items() if k in Contact.__dataclass_fields__})

    def by_type(self, relationship_type: str) -> list[Contact]:
        return [
            Contact(**{k: v for k, v in c.items() if k in Contact.__dataclass_fields__})
            for c in self._data["contacts"].values()
            if c.get("relationship_type") == relationship_type
        ]

    def log_interaction(self, interaction: Interaction) -> None:
        if not interaction.created_at:
            interaction.created_at = self._now()
        self._data.setdefault("interactions", []).append(interaction.to_dict())
        contact = self._data["contacts"].get(interaction.contact_id)
        if contact:
            contact["last_contact"] = interaction.occurred_at or self._now()
        self._save()

    def pending_follow_ups(self) -> list[Interaction]:
        return [
            Interaction(**{k: v for k, v in i.items() if k in Interaction.__dataclass_fields__})
            for i in self._data.get("interactions", [])
            if i.get("follow_up_needed")
        ]

    def dormant_contacts(self, days: int = 90) -> list[Contact]:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return [
            Contact(**{k: v for k, v in c.items() if k in Contact.__dataclass_fields__})
            for c in self._data["contacts"].values()
            if (c.get("last_contact") or "") < cutoff
        ]

    def to_context_string(self) -> str:
        total = len(self._data["contacts"])
        follow_ups = len(self.pending_follow_ups())
        dormant = len(self.dormant_contacts(90))
        parts = [f"Contacts: {total}"]
        if follow_ups:
            parts.append(f"Follow-ups pending: {follow_ups}")
        if dormant:
            parts.append(f"Dormant (90d): {dormant}")
        return " | ".join(parts)


store = RelationshipMemoryStore()
