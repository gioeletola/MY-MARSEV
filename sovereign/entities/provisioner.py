"""Entity Provisioner — master 7-step pipeline to connect anything to the OS."""
from __future__ import annotations

import logging
import re
import time
import uuid
from typing import TYPE_CHECKING

from sovereign.entities.entity_registry import (
    ConnectedEntity,
    Entity,
    EntityRegistry,
    EntityType,
    make_entity_id,
)
from sovereign.entities.vault_manager import EntityVault

if TYPE_CHECKING:
    from sovereign.integrations.integration_manager import IntegrationManager
    from sovereign.registries.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


class EntityProvisioner:
    """Orchestrates the 7-step entity provisioning pipeline.

    Also provides:
    - ``provision_from_text(text)`` — NER-style entity extraction from free text
    - ``provision_from_dict(data)`` — structured Entity creation
    """

    def __init__(
        self,
        entity_registry: EntityRegistry,
        vault_manager: EntityVault,
        integration_manager: "IntegrationManager | None" = None,
        agent_registry: "AgentRegistry | None" = None,
        scheduler: object = None,
    ) -> None:
        self._registry = entity_registry
        self._vault = vault_manager
        self._integration_manager = integration_manager
        self._agent_registry = agent_registry
        self._scheduler = scheduler
        self._sync_jobs: dict[str, str] = {}

    # ── Structured creation ───────────────────────────────────────────────

    def provision_from_dict(self, data: dict) -> Entity:
        """Create an Entity from a structured dict.

        Expected keys: name, entity_type, attributes (opt), tags (opt).
        """
        name = data.get("name") or data.get("title") or "Unnamed"
        raw_type = data.get("entity_type") or data.get("type") or "asset"
        # Normalise to EntityType value
        valid_types = {e.value for e in EntityType}
        entity_type = raw_type if raw_type in valid_types else EntityType.ASSET.value

        entity = Entity(
            entity_id=uuid.uuid4().hex[:8],
            name=name,
            entity_type=entity_type,
            attributes={k: v for k, v in data.items() if k not in ("name", "entity_type", "type", "tags")},
            tags=list(data.get("tags", [])),
        )
        return self._registry.upsert(entity)

    def provision_from_text(self, text: str) -> list[Entity]:
        """NER-style extraction: parse free text and create Entity records.

        Heuristics used:
        - Capitalised sequences → PERSON or COMPANY candidates
        - Phrases like "Project X" → PROJECT
        - Email-like tokens → PERSON
        - URL-like tokens → SERVICE
        - @mentions → PERSON (social)
        """
        entities: list[Entity] = []
        created_names: set[str] = set()

        def _make(name: str, entity_type: str, attributes: dict | None = None) -> Entity:
            if name in created_names:
                return self._registry.search(name, entity_type)[0] if \
                    self._registry.search(name, entity_type) else Entity(
                    entity_id=uuid.uuid4().hex[:8], name=name, entity_type=entity_type
                )
            created_names.add(name)
            e = Entity(
                entity_id=uuid.uuid4().hex[:8],
                name=name,
                entity_type=entity_type,
                attributes=attributes or {},
                tags=["auto-extracted"],
            )
            return self._registry.upsert(e)

        # Project patterns: "Project Foo", "the Bar project"
        for m in re.finditer(r'\bProject\s+([A-Z][A-Za-z0-9_-]+)', text):
            entities.append(_make(m.group(0), EntityType.PROJECT.value))

        # URL/service patterns
        for m in re.finditer(r'https?://([^\s/]+)', text):
            domain = m.group(1)
            entities.append(_make(domain, EntityType.SERVICE.value, {"url": m.group(0)}))

        # Email → person
        for m in re.finditer(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b', text):
            name = m.group(1).split("@")[0].replace(".", " ").title()
            entities.append(_make(name, EntityType.PERSON.value, {"email": m.group(1)}))

        # @mentions → person
        for m in re.finditer(r'@([A-Za-z0-9_]+)', text):
            entities.append(_make(m.group(1), EntityType.PERSON.value, {"handle": m.group(0)}))

        # Capitalised multi-word sequences (2-3 words, likely proper nouns)
        for m in re.finditer(r'\b([A-Z][a-z]+(?: [A-Z][a-z]+){1,2})\b', text):
            name = m.group(0)
            if name not in created_names and len(name) > 4:
                # Guess: if ends in Inc/Ltd/Corp → COMPANY, else PERSON
                entity_type = (
                    EntityType.COMPANY.value
                    if re.search(r'\b(Inc|Ltd|Corp|LLC|GmbH|plc)\b', name, re.I)
                    else EntityType.PERSON.value
                )
                entities.append(_make(name, entity_type))

        logger.info("EntityProvisioner.provision_from_text: extracted %d entities", len(entities))
        return entities

    # ── 7-step provisioning pipeline ──────────────────────────────────────

    def provision(
        self,
        name: str,
        category: str,
        connector_config: dict | None = None,
        agent_bindings: list[str] | None = None,
        files: list[str] | None = None,
        ui_panel: str = "dashboard",
        sync_interval_s: float = 3600.0,
        metadata: dict | None = None,
    ) -> ConnectedEntity:
        """Run all 7 provisioning steps and return the ConnectedEntity."""
        entity_id = make_entity_id()
        connector_id = ""
        vault_key = f"entity:{entity_id}"

        entity = ConnectedEntity(
            entity_id=entity_id,
            name=name,
            category=category,
            connector_id=connector_id,
            vault_key=vault_key,
            agent_bindings=list(agent_bindings or []),
            file_attachments=[],
            ui_panel=ui_panel,
            sync_interval_s=sync_interval_s,
            metadata=dict(metadata or {}),
            created_at=time.time(),
            last_synced=0.0,
            status="active",
        )
        self._registry.add(entity)
        logger.debug("Provisioner step 1: registered entity %s", entity_id)

        if connector_config:
            try:
                connector_type = connector_config.get("type", "")
                if self._integration_manager and connector_type:
                    from sovereign.integrations.base_integration import IntegrationConfig
                    cfg = IntegrationConfig(
                        integration_id=connector_type,
                        name=connector_type,
                        enabled=True,
                        credentials=connector_config.get("credentials", {}),
                    )
                    self._integration_manager.connect(connector_type, cfg)
                    entity.connector_id = connector_type
            except Exception as exc:
                logger.warning("Provisioner step 2: connector error (continuing) — %s", exc)

        try:
            self._vault.create_vault(entity_id, category)
        except Exception as exc:
            logger.warning("Provisioner step 3: vault error (continuing) — %s", exc)

        attached: list[str] = []
        for fp in files or []:
            try:
                fname = self._vault.attach_file(entity_id, fp)
                if fname:
                    attached.append(fname)
            except Exception as exc:
                logger.warning("Provisioner step 4: attach_file error (continuing) — %s", exc)
        entity.file_attachments = attached

        valid_bindings: list[str] = []
        for aid in agent_bindings or []:
            if self._agent_registry:
                agent = self._agent_registry.get(aid)
                if agent is None:
                    logger.warning("Provisioner step 5: agent %s not found, storing anyway", aid)
            valid_bindings.append(aid)
        entity.agent_bindings = valid_bindings

        entity.ui_panel = ui_panel

        if sync_interval_s > 0 and self._scheduler is not None:
            try:
                from sovereign.infra.scheduler import ScheduleFrequency
                job = self._scheduler.schedule(
                    name=f"entity_sync_{entity_id}",
                    agent_id="worker",
                    objective=f"Sync entity {entity_id} ({name})",
                    frequency=ScheduleFrequency.CUSTOM,
                    interval_seconds=int(sync_interval_s),
                    payload={"entity_id": entity_id},
                )
                self._sync_jobs[entity_id] = job.job_id
            except Exception as exc:
                logger.warning("Provisioner step 7: scheduler error (continuing) — %s", exc)

        self._registry._persist()
        logger.info("Provisioner: entity %s (%s) fully provisioned", entity_id, name)
        return entity

    def deprovision(self, entity_id: str) -> bool:
        entity = self._registry.get(entity_id)
        if entity is None:
            return False
        job_id = self._sync_jobs.pop(entity_id, None)
        if job_id and self._scheduler is not None:
            try:
                self._scheduler.unschedule(job_id)
            except Exception:
                pass
        try:
            self._vault.delete_vault(entity_id)
        except Exception:
            pass
        self._registry.remove(entity_id)
        return True

    def sync(self, entity_id: str) -> dict:
        entity = self._registry.get(entity_id)
        if entity is None:
            return {"ok": False, "error": f"Entity {entity_id} not found"}
        fetched: dict = {}
        error: str | None = None
        if self._integration_manager and entity.connector_id:
            connector = self._integration_manager.get(entity.connector_id)
            if connector is not None:
                try:
                    fetched = connector.fetch("all", {}) or {}
                except Exception as exc:
                    error = str(exc)
        for key, value in fetched.items():
            try:
                self._vault.write(entity_id, key, value)
            except Exception:
                pass
        self._registry.update_last_synced(entity_id)
        return {
            "ok": error is None,
            "entity_id": entity_id,
            "keys_synced": len(fetched),
            "error": error,
        }

    def list_entities(self, category: str = "") -> list[dict]:
        if category:
            entities = self._registry.list_by_category(category)
        else:
            entities = self._registry.list_all()
        return [e.to_dict() for e in entities]

    def get_entity_summary(self, entity_id: str) -> dict:
        entity = self._registry.get(entity_id)
        if entity is None:
            return {}
        vault_summary = {}
        try:
            vault_summary = self._vault.get_vault_summary(entity_id)
        except Exception:
            pass
        result = entity.to_dict()
        result["vault"] = vault_summary
        return result
