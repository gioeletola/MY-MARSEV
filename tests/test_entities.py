"""
Tests for the Connected Entity Provisioning System.

Covers:
  - TestEntityRegistry: add, get, list_by_category, remove, persistence
  - TestEntityVault: create_vault, write/read, attach_file, delete_vault, summary
  - TestEntityProvisioner: provision (all 7 steps), deprovision, sync, list_entities
"""
from __future__ import annotations

import time
import pytest

from sovereign.entities.entity_registry import (
    ConnectedEntity,
    EntityRegistry,
    make_entity_id,
)
from sovereign.entities.vault_manager import EntityVault
from sovereign.entities.provisioner import EntityProvisioner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(
    name: str = "Test Entity",
    category: str = "business",
    entity_id: str | None = None,
) -> ConnectedEntity:
    return ConnectedEntity(
        entity_id=entity_id or make_entity_id(),
        name=name,
        category=category,
        connector_id="",
        vault_key="entity:test",
        agent_bindings=[],
        file_attachments=[],
        ui_panel="dashboard",
        sync_interval_s=3600.0,
        metadata={},
        created_at=time.time(),
        last_synced=0.0,
        status="active",
    )


# ---------------------------------------------------------------------------
# TestEntityRegistry
# ---------------------------------------------------------------------------

class TestEntityRegistry:
    def test_add_and_get(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        entity = _make_entity("Acme", "business")
        reg.add(entity)
        got = reg.get(entity.entity_id)
        assert got is not None
        assert got.name == "Acme"
        assert got.category == "business"

    def test_add_duplicate_raises(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        entity = _make_entity("Dup")
        reg.add(entity)
        with pytest.raises(ValueError, match="already registered"):
            reg.add(entity)

    def test_get_nonexistent_returns_none(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        assert reg.get("nonexistent") is None

    def test_remove_entity(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        entity = _make_entity("Remove Me")
        reg.add(entity)
        ok = reg.remove(entity.entity_id)
        assert ok is True
        assert reg.get(entity.entity_id) is None

    def test_remove_nonexistent_returns_false(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        assert reg.remove("ghost") is False

    def test_list_all(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        for i in range(3):
            reg.add(_make_entity(f"Entity {i}"))
        assert len(reg.list_all()) == 3

    def test_list_by_category(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        reg.add(_make_entity("Biz1", "business"))
        reg.add(_make_entity("Biz2", "business"))
        reg.add(_make_entity("Dev1", "device"))
        biz = reg.list_by_category("business")
        assert len(biz) == 2
        assert all(e.category == "business" for e in biz)

    def test_list_by_category_empty(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        assert reg.list_by_category("social") == []

    def test_update_status(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        entity = _make_entity()
        reg.add(entity)
        ok = reg.update_status(entity.entity_id, "paused")
        assert ok is True
        assert reg.get(entity.entity_id).status == "paused"

    def test_update_status_nonexistent(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        assert reg.update_status("ghost", "error") is False

    def test_update_last_synced(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        entity = _make_entity()
        reg.add(entity)
        ts = time.time()
        ok = reg.update_last_synced(entity.entity_id, ts)
        assert ok is True
        assert reg.get(entity.entity_id).last_synced == ts

    def test_persistence(self, tmp_path):
        path = tmp_path / "reg.json"
        reg = EntityRegistry(path)
        entity = _make_entity("Persist Me", "personal")
        reg.add(entity)
        # Reload from disk
        reg2 = EntityRegistry(path)
        got = reg2.get(entity.entity_id)
        assert got is not None
        assert got.name == "Persist Me"
        assert got.category == "personal"

    def test_to_dict(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        entity = _make_entity("Dict Test")
        reg.add(entity)
        d = reg.to_dict()
        assert entity.entity_id in d
        assert d[entity.entity_id]["name"] == "Dict Test"

    def test_make_entity_id_unique(self):
        ids = {make_entity_id() for _ in range(100)}
        assert len(ids) == 100


# ---------------------------------------------------------------------------
# TestEntityVault
# ---------------------------------------------------------------------------

class TestEntityVault:
    def test_create_vault(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        ok = vault.create_vault("ent001", "business")
        assert ok is True
        assert (tmp_path / "vaults" / "ent001.json").exists()
        assert (tmp_path / "vaults" / "ent001" / "files").is_dir()

    def test_create_vault_idempotent(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent001")
        vault.create_vault("ent001")  # should not raise
        assert (tmp_path / "vaults" / "ent001.json").exists()

    def test_write_and_read(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent002")
        vault.write("ent002", "api_key", "secret123")
        assert vault.read("ent002", "api_key") == "secret123"

    def test_read_missing_key_returns_none(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent003")
        assert vault.read("ent003", "missing") is None

    def test_write_multiple_keys(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent004")
        vault.write("ent004", "k1", "v1")
        vault.write("ent004", "k2", 42)
        vault.write("ent004", "k3", {"nested": True})
        keys = vault.list_keys("ent004")
        assert set(keys) == {"k1", "k2", "k3"}

    def test_list_keys_excludes_meta(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent005", "device")
        keys = vault.list_keys("ent005")
        assert "_meta" not in keys

    def test_attach_file(self, tmp_path):
        # Create a source file
        src = tmp_path / "report.pdf"
        src.write_bytes(b"fake pdf content")
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent006")
        fname = vault.attach_file("ent006", src)
        assert fname == "report.pdf"
        assert (tmp_path / "vaults" / "ent006" / "files" / "report.pdf").exists()

    def test_attach_nonexistent_file_returns_none(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent007")
        result = vault.attach_file("ent007", tmp_path / "ghost.txt")
        assert result is None

    def test_list_files(self, tmp_path):
        src1 = tmp_path / "a.txt"
        src2 = tmp_path / "b.csv"
        src1.write_text("hello")
        src2.write_text("data")
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent008")
        vault.attach_file("ent008", src1)
        vault.attach_file("ent008", src2)
        files = vault.list_files("ent008")
        assert set(files) == {"a.txt", "b.csv"}

    def test_list_files_empty(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent009")
        assert vault.list_files("ent009") == []

    def test_delete_vault(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent010")
        vault.write("ent010", "k", "v")
        ok = vault.delete_vault("ent010")
        assert ok is True
        assert not (tmp_path / "vaults" / "ent010.json").exists()

    def test_delete_nonexistent_vault(self, tmp_path):
        vault = EntityVault(tmp_path / "vaults")
        # Should return False but not raise
        ok = vault.delete_vault("ghost_ent")
        assert ok is False

    def test_get_vault_summary(self, tmp_path):
        src = tmp_path / "doc.txt"
        src.write_text("hello world")
        vault = EntityVault(tmp_path / "vaults")
        vault.create_vault("ent011")
        vault.write("ent011", "key1", "val1")
        vault.write("ent011", "key2", 999)
        vault.attach_file("ent011", src)
        summary = vault.get_vault_summary("ent011")
        assert summary["entity_id"] == "ent011"
        assert summary["key_count"] == 2
        assert summary["file_count"] == 1
        assert summary["size_bytes"] > 0

    def test_auto_create_vault_on_write(self, tmp_path):
        """Write to a non-existent vault should auto-create it."""
        vault = EntityVault(tmp_path / "vaults")
        vault.write("ent_auto", "hello", "world")
        assert vault.read("ent_auto", "hello") == "world"


# ---------------------------------------------------------------------------
# TestEntityProvisioner
# ---------------------------------------------------------------------------

class TestEntityProvisioner:
    def _provisioner(self, tmp_path) -> EntityProvisioner:
        reg = EntityRegistry(tmp_path / "reg.json")
        vlt = EntityVault(tmp_path / "vaults")
        return EntityProvisioner(
            entity_registry=reg,
            vault_manager=vlt,
            integration_manager=None,
            agent_registry=None,
            scheduler=None,
        )

    def test_provision_returns_entity(self, tmp_path):
        p = self._provisioner(tmp_path)
        entity = p.provision(name="Stripe", category="account")
        assert entity.name == "Stripe"
        assert entity.category == "account"
        assert entity.entity_id
        assert entity.status == "active"

    def test_provision_step1_registers_entity(self, tmp_path):
        p = self._provisioner(tmp_path)
        entity = p.provision("MyBiz", "business")
        stored = p._registry.get(entity.entity_id)
        assert stored is not None
        assert stored.name == "MyBiz"

    def test_provision_step3_creates_vault(self, tmp_path):
        p = self._provisioner(tmp_path)
        entity = p.provision("Vault Test", "data_source")
        vault_path = tmp_path / "vaults" / f"{entity.entity_id}.json"
        assert vault_path.exists()

    def test_provision_step4_attaches_files(self, tmp_path):
        src = tmp_path / "data.csv"
        src.write_text("a,b,c\n1,2,3")
        p = self._provisioner(tmp_path)
        entity = p.provision("FileEntity", "data_source", files=[str(src)])
        assert "data.csv" in entity.file_attachments

    def test_provision_step5_binds_agents(self, tmp_path):
        p = self._provisioner(tmp_path)
        entity = p.provision("AgentBound", "business", agent_bindings=["ceo", "worker"])
        assert "ceo" in entity.agent_bindings
        assert "worker" in entity.agent_bindings

    def test_provision_step6_sets_ui_panel(self, tmp_path):
        p = self._provisioner(tmp_path)
        entity = p.provision("Sidebar Entity", "social", ui_panel="sidebar")
        assert entity.ui_panel == "sidebar"

    def test_provision_step7_skipped_when_no_scheduler(self, tmp_path):
        """No scheduler — should not raise, just skip."""
        p = self._provisioner(tmp_path)
        entity = p.provision("NoScheduler", "device", sync_interval_s=60.0)
        assert entity.entity_id not in p._sync_jobs

    def test_provision_step7_schedules_with_scheduler(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        vlt = EntityVault(tmp_path / "vaults")
        from sovereign.infra.scheduler import Scheduler
        sched = Scheduler(tmp_path / "sched.json")
        p = EntityProvisioner(reg, vlt, scheduler=sched)
        entity = p.provision("Scheduled", "account", sync_interval_s=7200.0)
        assert entity.entity_id in p._sync_jobs
        job_names = [j.name for j in sched.list_jobs()]
        assert any("entity_sync_" in n for n in job_names)

    def test_provision_graceful_degradation_missing_connector(self, tmp_path):
        """Bad connector_config should not cause provision to fail."""
        p = self._provisioner(tmp_path)
        entity = p.provision(
            "Graceful",
            "external_ai",
            connector_config={"type": "nonexistent_connector"},
        )
        assert entity is not None
        assert entity.status == "active"

    def test_provision_metadata(self, tmp_path):
        p = self._provisioner(tmp_path)
        meta = {"region": "EU", "tier": "premium"}
        entity = p.provision("MetaEnt", "business", metadata=meta)
        assert entity.metadata["region"] == "EU"
        assert entity.metadata["tier"] == "premium"

    def test_provision_manual_sync(self, tmp_path):
        """sync_interval_s=0 means manual only — no scheduler job."""
        reg = EntityRegistry(tmp_path / "reg.json")
        vlt = EntityVault(tmp_path / "vaults")
        from sovereign.infra.scheduler import Scheduler
        sched = Scheduler(tmp_path / "sched.json")
        p = EntityProvisioner(reg, vlt, scheduler=sched)
        entity = p.provision("Manual", "device", sync_interval_s=0.0)
        assert entity.entity_id not in p._sync_jobs

    def test_deprovision_removes_entity(self, tmp_path):
        p = self._provisioner(tmp_path)
        entity = p.provision("ToRemove", "account")
        ok = p.deprovision(entity.entity_id)
        assert ok is True
        assert p._registry.get(entity.entity_id) is None

    def test_deprovision_removes_vault(self, tmp_path):
        p = self._provisioner(tmp_path)
        entity = p.provision("VaultRemove", "data_source")
        vault_path = tmp_path / "vaults" / f"{entity.entity_id}.json"
        assert vault_path.exists()
        p.deprovision(entity.entity_id)
        assert not vault_path.exists()

    def test_deprovision_nonexistent_returns_false(self, tmp_path):
        p = self._provisioner(tmp_path)
        assert p.deprovision("ghost") is False

    def test_deprovision_removes_sync_job(self, tmp_path):
        reg = EntityRegistry(tmp_path / "reg.json")
        vlt = EntityVault(tmp_path / "vaults")
        from sovereign.infra.scheduler import Scheduler
        sched = Scheduler(tmp_path / "sched.json")
        p = EntityProvisioner(reg, vlt, scheduler=sched)
        entity = p.provision("SyncRemove", "account", sync_interval_s=3600.0)
        job_id = p._sync_jobs.get(entity.entity_id)
        assert job_id is not None
        p.deprovision(entity.entity_id)
        assert entity.entity_id not in p._sync_jobs
        # Job should be unscheduled
        remaining = [j.job_id for j in sched.list_jobs()]
        assert job_id not in remaining

    def test_sync_no_connector(self, tmp_path):
        """Sync with no integration_manager should succeed with 0 keys synced."""
        p = self._provisioner(tmp_path)
        entity = p.provision("SyncNoConn", "personal")
        result = p.sync(entity.entity_id)
        assert result["ok"] is True
        assert result["entity_id"] == entity.entity_id
        assert result["keys_synced"] == 0

    def test_sync_nonexistent_entity(self, tmp_path):
        p = self._provisioner(tmp_path)
        result = p.sync("ghost")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_sync_updates_last_synced(self, tmp_path):
        p = self._provisioner(tmp_path)
        entity = p.provision("SyncTime", "device")
        assert entity.last_synced == 0.0
        p.sync(entity.entity_id)
        updated = p._registry.get(entity.entity_id)
        assert updated.last_synced > 0.0

    def test_list_entities_all(self, tmp_path):
        p = self._provisioner(tmp_path)
        p.provision("E1", "business")
        p.provision("E2", "device")
        p.provision("E3", "social")
        result = p.list_entities()
        assert len(result) == 3
        names = {r["name"] for r in result}
        assert names == {"E1", "E2", "E3"}

    def test_list_entities_by_category(self, tmp_path):
        p = self._provisioner(tmp_path)
        p.provision("B1", "business")
        p.provision("B2", "business")
        p.provision("D1", "device")
        biz = p.list_entities(category="business")
        assert len(biz) == 2
        assert all(e["category"] == "business" for e in biz)

    def test_list_entities_empty(self, tmp_path):
        p = self._provisioner(tmp_path)
        assert p.list_entities() == []

    def test_get_entity_summary(self, tmp_path):
        src = tmp_path / "file.txt"
        src.write_text("content")
        p = self._provisioner(tmp_path)
        entity = p.provision("Summary", "data_source", files=[str(src)])
        summary = p.get_entity_summary(entity.entity_id)
        assert summary["entity_id"] == entity.entity_id
        assert summary["name"] == "Summary"
        assert "vault" in summary
        assert summary["vault"]["file_count"] == 1

    def test_get_entity_summary_nonexistent(self, tmp_path):
        p = self._provisioner(tmp_path)
        assert p.get_entity_summary("ghost") == {}

    def test_provision_with_integration_manager(self, tmp_path):
        """Provision with a real IntegrationManager (connector may not connect but no crash)."""
        from sovereign.integrations.integration_manager import IntegrationManager
        reg = EntityRegistry(tmp_path / "reg.json")
        vlt = EntityVault(tmp_path / "vaults")
        im = IntegrationManager()
        p = EntityProvisioner(reg, vlt, integration_manager=im)
        # "email" is a valid connector type
        entity = p.provision(
            "EmailConn",
            "account",
            connector_config={"type": "email", "credentials": {}},
        )
        assert entity is not None
        assert entity.entity_id
