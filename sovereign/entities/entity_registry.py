"""Entity Registry — persisted store of all ConnectedEntity records."""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path("data/memory/entity_registry.json")

VALID_CATEGORIES = frozenset(
    {"business", "device", "account", "social", "external_ai", "personal", "data_source"}
)
VALID_STATUSES = frozenset({"active", "paused", "error"})
VALID_UI_PANELS = frozenset({"dashboard", "sidebar", "hidden"})


@dataclass
class ConnectedEntity:
    entity_id: str
    name: str
    category: str  # "business"|"device"|"account"|"social"|"external_ai"|"personal"|"data_source"
    connector_id: str  # references IntegrationManager connector
    vault_key: str  # memory vault namespace
    agent_bindings: list[str]  # agent IDs authorized to access
    file_attachments: list[str]  # paths/keys
    ui_panel: str  # "dashboard"|"sidebar"|"hidden"
    sync_interval_s: float  # 0 = manual only
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_synced: float = 0.0
    status: str = "active"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConnectedEntity":
        return cls(**data)


class EntityRegistry:
    """Persisted registry of ConnectedEntity records.

    Backed by ``data/memory/entity_registry.json``.
    """

    def __init__(self, data_path: str | Path = _DEFAULT_PATH) -> None:
        self._path = Path(data_path)
        self._entities: dict[str, ConnectedEntity] = {}
        self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, entity: ConnectedEntity) -> ConnectedEntity:
        """Add a new entity. Raises ValueError on duplicate entity_id."""
        if entity.entity_id in self._entities:
            raise ValueError(f"Entity already registered: {entity.entity_id}")
        self._entities[entity.entity_id] = entity
        self._persist()
        logger.debug("EntityRegistry: added entity %s (%s)", entity.entity_id, entity.name)
        return entity

    def get(self, entity_id: str) -> ConnectedEntity | None:
        """Return entity by ID, or None."""
        return self._entities.get(entity_id)

    def remove(self, entity_id: str) -> bool:
        """Remove entity by ID. Returns True if found and removed."""
        if entity_id not in self._entities:
            return False
        del self._entities[entity_id]
        self._persist()
        logger.debug("EntityRegistry: removed entity %s", entity_id)
        return True

    def update_status(self, entity_id: str, status: str) -> bool:
        """Update entity status. Returns False if entity not found."""
        entity = self._entities.get(entity_id)
        if entity is None:
            return False
        entity.status = status
        self._persist()
        return True

    def update_last_synced(self, entity_id: str, ts: float | None = None) -> bool:
        """Update last_synced timestamp."""
        entity = self._entities.get(entity_id)
        if entity is None:
            return False
        entity.last_synced = ts if ts is not None else time.time()
        self._persist()
        return True

    def list_all(self) -> list[ConnectedEntity]:
        """Return all registered entities."""
        return list(self._entities.values())

    def list_by_category(self, category: str) -> list[ConnectedEntity]:
        """Return entities filtered by category."""
        return [e for e in self._entities.values() if e.category == category]

    def to_dict(self) -> dict:
        """Serialise full registry to a plain dict."""
        return {eid: e.to_dict() for eid, e in self._entities.items()}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("EntityRegistry: persist failed — %s", exc)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for eid, data in raw.items():
                self._entities[eid] = ConnectedEntity.from_dict(data)
            logger.debug("EntityRegistry: loaded %d entities", len(self._entities))
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            logger.warning("EntityRegistry: could not load — %s", exc)


def make_entity_id() -> str:
    """Generate a short UUID-based entity ID."""
    return uuid.uuid4().hex[:8]
