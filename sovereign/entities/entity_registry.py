"""Entity Registry — persisted store of all entity records."""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path("data/memory/entity_registry.json")

# ── Legacy constants (kept for backward compat) ───────────────────────────────
VALID_CATEGORIES = frozenset(
    {"business", "device", "account", "social", "external_ai", "personal", "data_source"}
)
VALID_STATUSES = frozenset({"active", "paused", "error"})
VALID_UI_PANELS = frozenset({"dashboard", "sidebar", "hidden"})


# ── New entity model ──────────────────────────────────────────────────────────

class EntityType(str, Enum):
    PERSON = "person"
    COMPANY = "company"
    PROJECT = "project"
    ASSET = "asset"
    LOCATION = "location"
    EVENT = "event"
    PRODUCT = "product"
    SERVICE = "service"


@dataclass
class Entity:
    entity_id: str
    name: str
    entity_type: str                            # EntityType.value
    attributes: dict[str, Any] = field(default_factory=dict)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        return cls(**data)

    def _touch(self) -> None:
        self.updated_at = time.time()


# ── Legacy ConnectedEntity (kept for backward compat) ─────────────────────────

@dataclass
class ConnectedEntity:
    entity_id: str
    name: str
    category: str
    connector_id: str
    vault_key: str
    agent_bindings: list[str]
    file_attachments: list[str]
    ui_panel: str
    sync_interval_s: float
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_synced: float = 0.0
    status: str = "active"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConnectedEntity":
        return cls(**data)


# ── Entity Registry ───────────────────────────────────────────────────────────

class EntityRegistry:
    """Persisted registry of Entity records with graph-relationship support.

    Backwards-compatible with the old ConnectedEntity-based registry.
    """

    def __init__(self, data_path: str | Path = _DEFAULT_PATH) -> None:
        self._path = Path(data_path)
        # New model
        self._entities: dict[str, Entity] = {}
        # Legacy model
        self._connected: dict[str, ConnectedEntity] = {}
        self._load()

    # ── CRUD ──────────────────────────────────────────────────────────────

    def upsert(self, entity: Entity) -> Entity:
        """Insert or update an Entity. Returns the stored Entity."""
        entity._touch()
        self._entities[entity.entity_id] = entity
        self._persist()
        logger.debug("EntityRegistry.upsert: %s (%s)", entity.entity_id, entity.name)
        return entity

    def get_entity(self, entity_id: str) -> Entity | None:
        return self._entities.get(entity_id)

    def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            self._persist()
            return True
        return False

    def list_entities(self, entity_type: str | None = None) -> list[Entity]:
        items = list(self._entities.values())
        if entity_type:
            items = [e for e in items if e.entity_type == entity_type]
        return items

    # ── Search ────────────────────────────────────────────────────────────

    def search(self, query: str, entity_type: str | None = None) -> list[Entity]:
        """Full-text search over name, tags, and attribute values.

        Returns matching entities sorted by relevance (name match first).
        """
        q = query.lower().strip()
        if not q:
            return self.list_entities(entity_type)

        candidates = self.list_entities(entity_type)
        scored: list[tuple[int, Entity]] = []

        for entity in candidates:
            score = 0
            if q in entity.name.lower():
                score += 10
            if any(q in tag.lower() for tag in entity.tags):
                score += 5
            for v in entity.attributes.values():
                if q in str(v).lower():
                    score += 2
            if score > 0:
                scored.append((score, entity))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored]

    # ── Relationships ─────────────────────────────────────────────────────

    def relate(
        self,
        entity_a_id: str,
        rel_type: str,
        entity_b_id: str,
        weight: float = 1.0,
    ) -> bool:
        """Create a directed relationship from A → B."""
        a = self._entities.get(entity_a_id)
        b = self._entities.get(entity_b_id)
        if not a or not b:
            logger.warning(
                "EntityRegistry.relate: one or both entities not found (%s, %s)",
                entity_a_id, entity_b_id,
            )
            return False
        rel = {
            "rel_type": rel_type,
            "target_id": entity_b_id,
            "weight": weight,
            "created_at": time.time(),
        }
        # Avoid duplicate
        existing = [
            r for r in a.relationships
            if r.get("target_id") == entity_b_id and r.get("rel_type") == rel_type
        ]
        if not existing:
            a.relationships.append(rel)
            a._touch()
            self._persist()
        return True

    def graph_neighbors(self, entity_id: str, depth: int = 2) -> list[Entity]:
        """Return all entities reachable within *depth* relationship hops."""
        visited: set[str] = {entity_id}
        frontier: set[str] = {entity_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for eid in frontier:
                entity = self._entities.get(eid)
                if not entity:
                    continue
                for rel in entity.relationships:
                    tid = rel.get("target_id", "")
                    if tid and tid not in visited:
                        visited.add(tid)
                        next_frontier.add(tid)
            frontier = next_frontier

        visited.discard(entity_id)
        return [self._entities[eid] for eid in visited if eid in self._entities]

    def merge(self, entity_a_id: str, entity_b_id: str) -> Entity:
        """Merge entity B into entity A, combining attributes and relationships.

        Entity B is removed from the registry after merge.
        """
        a = self._entities.get(entity_a_id)
        b = self._entities.get(entity_b_id)
        if not a:
            raise KeyError(f"Entity {entity_a_id} not found")
        if not b:
            raise KeyError(f"Entity {entity_b_id} not found")

        # Merge attributes (A wins on conflict)
        for k, v in b.attributes.items():
            if k not in a.attributes:
                a.attributes[k] = v

        # Merge tags
        for tag in b.tags:
            if tag not in a.tags:
                a.tags.append(tag)

        # Adopt B's relationships, rewriting self-references
        for rel in b.relationships:
            if rel.get("target_id") != entity_a_id:
                a.relationships.append(rel)

        # Redirect any relationships pointing to B → A
        for entity in self._entities.values():
            for rel in entity.relationships:
                if rel.get("target_id") == entity_b_id:
                    rel["target_id"] = entity_a_id

        del self._entities[entity_b_id]
        a._touch()
        self._persist()
        logger.info("EntityRegistry.merge: merged %s into %s", entity_b_id, entity_a_id)
        return a

    # ── Legacy ConnectedEntity API ────────────────────────────────────────

    def add(self, entity: ConnectedEntity) -> ConnectedEntity:
        if entity.entity_id in self._connected:
            raise ValueError(f"Entity already registered: {entity.entity_id}")
        self._connected[entity.entity_id] = entity
        self._persist()
        return entity

    def get(self, entity_id: str) -> ConnectedEntity | None:
        return self._connected.get(entity_id)

    def remove(self, entity_id: str) -> bool:
        if entity_id not in self._connected:
            return False
        del self._connected[entity_id]
        self._persist()
        return True

    def update_status(self, entity_id: str, status: str) -> bool:
        entity = self._connected.get(entity_id)
        if entity is None:
            return False
        entity.status = status
        self._persist()
        return True

    def update_last_synced(self, entity_id: str, ts: float | None = None) -> bool:
        entity = self._connected.get(entity_id)
        if entity is None:
            return False
        entity.last_synced = ts if ts is not None else time.time()
        self._persist()
        return True

    def list_all(self) -> list[ConnectedEntity]:
        return list(self._connected.values())

    def list_by_category(self, category: str) -> list[ConnectedEntity]:
        return [e for e in self._connected.values() if e.category == category]

    def to_dict(self) -> dict:
        return {eid: e.to_dict() for eid, e in self._connected.items()}

    # ── Persistence ───────────────────────────────────────────────────────

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "_entities": {eid: e.to_dict() for eid, e in self._entities.items()},
                "_connected": {eid: e.to_dict() for eid, e in self._connected.items()},
            }
            self._path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            logger.error("EntityRegistry._persist failed — %s", exc)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "_entities" in raw:
                # New format
                for eid, data in raw.get("_entities", {}).items():
                    self._entities[eid] = Entity.from_dict(data)
                for eid, data in raw.get("_connected", {}).items():
                    self._connected[eid] = ConnectedEntity.from_dict(data)
            elif isinstance(raw, dict):
                # Old format: all ConnectedEntity
                for eid, data in raw.items():
                    self._connected[eid] = ConnectedEntity.from_dict(data)
            logger.debug(
                "EntityRegistry: loaded %d entities, %d connected",
                len(self._entities), len(self._connected),
            )
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            logger.warning("EntityRegistry._load failed — %s", exc)


def make_entity_id() -> str:
    return uuid.uuid4().hex[:8]
