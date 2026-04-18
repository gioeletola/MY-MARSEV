"""Entity Provisioner — master 7-step pipeline to connect anything to the OS."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from sovereign.entities.entity_registry import (
    ConnectedEntity,
    EntityRegistry,
    make_entity_id,
)
from sovereign.entities.vault_manager import EntityVault

if TYPE_CHECKING:
    from sovereign.integrations.integration_manager import IntegrationManager
    from sovereign.registries.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


class EntityProvisioner:
    """Orchestrates the 7-step entity provisioning pipeline.

    Steps:
      1. Register entity in EntityRegistry
      2. Create/connect connector via IntegrationManager
      3. Create dedicated vault via EntityVault
      4. Attach files
      5. Bind agents (stored on entity)
      6. Set UI panel
      7. Schedule sync job (if sync_interval_s > 0)
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
        # Map entity_id → scheduler job_id
        self._sync_jobs: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Main provisioning API
    # ------------------------------------------------------------------

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
        """Run all 7 provisioning steps and return the ConnectedEntity.

        Gracefully degrades on connector/file errors — always returns an entity.
        """
        entity_id = make_entity_id()
        connector_id = ""
        vault_key = f"entity:{entity_id}"

        # ---- Step 1: Register entity -----------------------------------
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

        # ---- Step 2: Connector -----------------------------------------
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
                    ok = self._integration_manager.connect(connector_type, cfg)
                    if ok:
                        entity.connector_id = connector_type
                        logger.debug(
                            "Provisioner step 2: connected connector %s", connector_type
                        )
                    else:
                        logger.warning(
                            "Provisioner step 2: connector %s returned False, continuing",
                            connector_type,
                        )
                        entity.connector_id = connector_type
            except Exception as exc:
                logger.warning("Provisioner step 2: connector error (continuing) — %s", exc)

        # ---- Step 3: Create dedicated vault ----------------------------
        try:
            self._vault.create_vault(entity_id, category)
            logger.debug("Provisioner step 3: vault created for %s", entity_id)
        except Exception as exc:
            logger.warning("Provisioner step 3: vault error (continuing) — %s", exc)

        # ---- Step 4: Attach files --------------------------------------
        attached: list[str] = []
        for fp in files or []:
            try:
                fname = self._vault.attach_file(entity_id, fp)
                if fname:
                    attached.append(fname)
            except Exception as exc:
                logger.warning("Provisioner step 4: attach_file error (continuing) — %s", exc)
        entity.file_attachments = attached
        logger.debug("Provisioner step 4: attached %d files", len(attached))

        # ---- Step 5: Bind agents (validate if registry available) ------
        valid_bindings: list[str] = []
        for aid in agent_bindings or []:
            if self._agent_registry:
                agent = self._agent_registry.get(aid)
                if agent is None:
                    logger.warning(
                        "Provisioner step 5: agent %s not found, storing binding anyway", aid
                    )
            valid_bindings.append(aid)
        entity.agent_bindings = valid_bindings
        logger.debug("Provisioner step 5: bound %d agents", len(valid_bindings))

        # ---- Step 6: Set UI panel --------------------------------------
        entity.ui_panel = ui_panel
        logger.debug("Provisioner step 6: UI panel set to %s", ui_panel)

        # ---- Step 7: Schedule sync job ---------------------------------
        if sync_interval_s > 0 and self._scheduler is not None:
            try:
                from sovereign.infra.scheduler import ScheduleFrequency

                job = self._scheduler.schedule(
                    name=f"entity_sync_{entity_id}",
                    agent_id="worker",
                    objective=f"Sync entity {entity_id} ({name}) from connector {entity.connector_id}",
                    frequency=ScheduleFrequency.CUSTOM,
                    interval_seconds=int(sync_interval_s),
                    payload={"entity_id": entity_id},
                )
                self._sync_jobs[entity_id] = job.job_id
                logger.debug(
                    "Provisioner step 7: scheduled sync job %s for entity %s",
                    job.job_id,
                    entity_id,
                )
            except Exception as exc:
                logger.warning("Provisioner step 7: scheduler error (continuing) — %s", exc)

        # Persist final state of entity
        self._registry._persist()
        logger.info("Provisioner: entity %s (%s) fully provisioned", entity_id, name)
        return entity

    # ------------------------------------------------------------------
    # Deprovision
    # ------------------------------------------------------------------

    def deprovision(self, entity_id: str) -> bool:
        """Remove entity, vault, bindings, and scheduled sync job."""
        entity = self._registry.get(entity_id)
        if entity is None:
            logger.warning("Provisioner.deprovision: entity %s not found", entity_id)
            return False

        # Remove scheduler job
        job_id = self._sync_jobs.pop(entity_id, None)
        if job_id and self._scheduler is not None:
            try:
                self._scheduler.unschedule(job_id)
            except Exception as exc:
                logger.warning("Provisioner.deprovision: scheduler remove error — %s", exc)

        # Delete vault
        try:
            self._vault.delete_vault(entity_id)
        except Exception as exc:
            logger.warning("Provisioner.deprovision: vault delete error — %s", exc)

        # Remove from registry
        self._registry.remove(entity_id)
        logger.info("Provisioner: deprovisioned entity %s", entity_id)
        return True

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def sync(self, entity_id: str) -> dict:
        """Trigger a manual sync: fetch from connector and write to vault."""
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
                    logger.warning("Provisioner.sync: fetch error for %s — %s", entity_id, exc)
            else:
                logger.debug(
                    "Provisioner.sync: connector %s not found, skipping fetch",
                    entity.connector_id,
                )

        # Write fetched data to vault
        for key, value in fetched.items():
            try:
                self._vault.write(entity_id, key, value)
            except Exception as exc:
                logger.warning("Provisioner.sync: vault write error — %s", exc)

        # Update last_synced
        self._registry.update_last_synced(entity_id)
        entity.last_synced = time.time()

        return {
            "ok": error is None,
            "entity_id": entity_id,
            "keys_synced": len(fetched),
            "error": error,
        }

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def list_entities(self, category: str = "") -> list[dict]:
        """List all entities, optionally filtered by category."""
        if category:
            entities = self._registry.list_by_category(category)
        else:
            entities = self._registry.list_all()
        return [e.to_dict() for e in entities]

    def get_entity_summary(self, entity_id: str) -> dict:
        """Return full summary: entity data + vault stats + last sync."""
        entity = self._registry.get(entity_id)
        if entity is None:
            return {}
        vault_summary = {}
        try:
            vault_summary = self._vault.get_vault_summary(entity_id)
        except Exception as exc:
            logger.warning("Provisioner.get_entity_summary: vault summary error — %s", exc)
        result = entity.to_dict()
        result["vault"] = vault_summary
        return result
