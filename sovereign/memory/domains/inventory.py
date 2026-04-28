"""Memory domain: inventory — physical assets, equipment, subscriptions, consumables."""
from __future__ import annotations

import json
from sovereign.memory._atomic_io import _save_json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/inventory.json")
DOMAIN_NAME = "inventory"


@dataclass
class InventoryItem:
    item_id: str
    name: str
    category: str = "general"        # electronics | furniture | clothing | food | tool | software
    quantity: float = 1.0
    unit: str = "unit"
    location: str = ""
    purchase_price: float = 0.0
    current_value: float = 0.0
    purchase_date: str = ""
    expiry_date: str = ""
    serial_number: str = ""
    condition: str = "good"           # new | good | fair | poor | broken
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InventoryMemoryStore:
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
        return {"items": {}}

    def _save(self) -> None:
        _save_json(self._path, self._data)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_item(self, item: InventoryItem) -> None:
        if not item.created_at:
            item.created_at = self._now()
        item.updated_at = self._now()
        self._data["items"][item.item_id] = item.to_dict()
        self._save()

    def update_item(self, item_id: str, **kwargs: Any) -> None:
        item = self._data["items"].get(item_id)
        if item:
            item.update(kwargs)
            item["updated_at"] = self._now()
            self._save()

    def get_item(self, item_id: str) -> InventoryItem | None:
        raw = self._data["items"].get(item_id)
        if raw is None:
            return None
        return InventoryItem(**{k: v for k, v in raw.items() if k in InventoryItem.__dataclass_fields__})

    def by_category(self, category: str) -> list[InventoryItem]:
        return [
            InventoryItem(**{k: v for k, v in i.items() if k in InventoryItem.__dataclass_fields__})
            for i in self._data["items"].values()
            if i.get("category") == category
        ]

    def expiring_soon(self, days: int = 30) -> list[InventoryItem]:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
        return [
            InventoryItem(**{k: v for k, v in i.items() if k in InventoryItem.__dataclass_fields__})
            for i in self._data["items"].values()
            if i.get("expiry_date") and i["expiry_date"] <= cutoff
        ]

    def total_value(self) -> float:
        return sum(
            i.get("current_value", 0.0) * i.get("quantity", 1.0)
            for i in self._data["items"].values()
        )

    def all_items(self) -> list[InventoryItem]:
        return [
            InventoryItem(**{k: v for k, v in i.items() if k in InventoryItem.__dataclass_fields__})
            for i in self._data["items"].values()
        ]

    def to_context_string(self) -> str:
        count = len(self._data["items"])
        total = self.total_value()
        expiring = len(self.expiring_soon(30))
        parts = [f"Items: {count}", f"Total value: {total:.2f}"]
        if expiring:
            parts.append(f"Expiring soon: {expiring}")
        return " | ".join(parts)


store = InventoryMemoryStore()
