"""
Tests for governance (ChangeManagement) and mode-specific features.
Targets 0%-40% coverage modules.
"""
from __future__ import annotations

import pytest


# ===========================================================================
# ChangeManagement
# ===========================================================================

class TestChangeManagement:
    @pytest.fixture
    def cm(self, tmp_path):
        from sovereign.governance.change_management import ChangeManagement
        return ChangeManagement(persist_path=tmp_path / "changes.jsonl")

    @pytest.fixture
    def change_type(self):
        from sovereign.governance.change_management import ChangeType
        return ChangeType.CONFIG

    def _propose(self, cm, change_type, title="Test Change"):
        return cm.propose(
            title=title,
            description="A test change",
            change_type=change_type,
            proposed_by="admin@test.com",
            risk_level="low",
            rollback_plan="Revert config",
        )

    def test_propose_creates_record(self, cm, change_type):
        record = self._propose(cm, change_type)
        assert record.title == "Test Change"
        assert record.change_id is not None

    def test_propose_status_is_proposed(self, cm, change_type):
        from sovereign.governance.change_management import ChangeStatus
        record = self._propose(cm, change_type)
        assert record.status == ChangeStatus.PROPOSED

    def test_approve_success(self, cm, change_type):
        record = self._propose(cm, change_type)
        ok = cm.approve(record.change_id, approved_by="owner@test.com")
        assert ok is True
        assert cm.get(record.change_id).approved_by == "owner@test.com"

    def test_approve_unknown_id(self, cm):
        ok = cm.approve("nonexistent-id", approved_by="owner@test.com")
        assert ok is False

    def test_approve_wrong_status(self, cm, change_type):
        record = self._propose(cm, change_type)
        cm.approve(record.change_id, "owner")
        ok = cm.approve(record.change_id, "owner2")
        assert ok is False

    def test_reject_success(self, cm, change_type):
        from sovereign.governance.change_management import ChangeStatus
        record = self._propose(cm, change_type)
        ok = cm.reject(record.change_id, reason="Not needed")
        assert ok is True
        assert cm.get(record.change_id).status == ChangeStatus.REJECTED

    def test_reject_unknown_id(self, cm):
        ok = cm.reject("nonexistent", reason="bad")
        assert ok is False

    def test_reject_wrong_status(self, cm, change_type):
        record = self._propose(cm, change_type)
        cm.approve(record.change_id, "owner")
        ok = cm.reject(record.change_id, reason="too late")
        assert ok is False

    def test_deploy_success(self, cm, change_type):
        from sovereign.governance.change_management import ChangeStatus
        record = self._propose(cm, change_type)
        cm.approve(record.change_id, "owner")
        ok = cm.deploy(record.change_id)
        assert ok is True
        assert cm.get(record.change_id).status == ChangeStatus.DEPLOYED

    def test_deploy_not_approved(self, cm, change_type):
        record = self._propose(cm, change_type)
        ok = cm.deploy(record.change_id)
        assert ok is False

    def test_deploy_unknown_id(self, cm):
        ok = cm.deploy("nonexistent")
        assert ok is False

    def test_rollback_success(self, cm, change_type):
        from sovereign.governance.change_management import ChangeStatus
        record = self._propose(cm, change_type)
        cm.approve(record.change_id, "owner")
        cm.deploy(record.change_id)
        ok = cm.rollback(record.change_id)
        assert ok is True
        assert cm.get(record.change_id).status == ChangeStatus.ROLLED_BACK

    def test_rollback_not_deployed(self, cm, change_type):
        record = self._propose(cm, change_type)
        cm.approve(record.change_id, "owner")
        ok = cm.rollback(record.change_id)
        assert ok is False

    def test_rollback_unknown_id(self, cm):
        ok = cm.rollback("nonexistent")
        assert ok is False

    def test_pending_returns_proposed(self, cm, change_type):
        self._propose(cm, change_type, "P1")
        self._propose(cm, change_type, "P2")
        pending = cm.pending()
        assert len(pending) == 2

    def test_pending_excludes_deployed(self, cm, change_type):
        record = self._propose(cm, change_type, "Deploy")
        cm.approve(record.change_id, "owner")
        cm.deploy(record.change_id)
        pending = cm.pending()
        assert not any(r.change_id == record.change_id for r in pending)

    def test_get_returns_record(self, cm, change_type):
        record = self._propose(cm, change_type)
        fetched = cm.get(record.change_id)
        assert fetched is not None
        assert fetched.title == "Test Change"

    def test_get_unknown_returns_none(self, cm):
        assert cm.get("unknown") is None

    def test_all_records(self, cm, change_type):
        self._propose(cm, change_type, "R1")
        self._propose(cm, change_type, "R2")
        records = cm.all_records()
        assert len(records) == 2

    def test_persistence(self, tmp_path, change_type):
        from sovereign.governance.change_management import ChangeManagement
        path = tmp_path / "persist.jsonl"
        cm1 = ChangeManagement(persist_path=path)
        record = cm1.propose(
            title="Persistent", description="",
            change_type=change_type, proposed_by="test",
            risk_level="low", rollback_plan="",
        )
        cm2 = ChangeManagement(persist_path=path)
        assert cm2.get(record.change_id) is not None

    def test_to_dict(self, cm, change_type):
        record = self._propose(cm, change_type)
        d = record.to_dict()
        assert d["title"] == "Test Change"
        assert "change_id" in d

    def test_from_dict(self, change_type):
        from sovereign.governance.change_management import ChangeRecord, ChangeStatus
        d = {
            "change_id": "abc123",
            "change_type": "config",
            "title": "From Dict",
            "description": "desc",
            "proposed_by": "user",
            "status": "proposed",
            "risk_level": "low",
            "rollback_plan": "plan",
            "approved_by": "",
            "deployed_at": "",
            "created_at": "2026-01-01T00:00:00",
        }
        record = ChangeRecord.from_dict(d)
        assert record.title == "From Dict"
        assert record.status == ChangeStatus.PROPOSED

    def test_all_change_types(self):
        from sovereign.governance.change_management import ChangeType
        for ct in ChangeType:
            assert ct.value is not None

    def test_all_change_statuses(self):
        from sovereign.governance.change_management import ChangeStatus
        for cs in ChangeStatus:
            assert cs.value is not None


# ===========================================================================
# LocalOfflineMode
# ===========================================================================

class TestLocalOfflineMode:
    @pytest.fixture
    def mode(self, tmp_path):
        from sovereign.modes.local_offline_mode import Local_offlineMode
        return Local_offlineMode(data_dir=str(tmp_path))

    def test_name(self, mode):
        assert mode.name == "local_offline"

    def test_is_online_initially_none(self, mode):
        assert mode.is_online is None

    def test_filter_tools_when_offline(self, mode):
        mode._online = False
        allowed = mode.filter_tools(["web_search", "code_exec", "file_ops", "browser"])
        assert "web_search" not in allowed
        assert "code_exec" in allowed
        assert "file_ops" in allowed

    def test_filter_tools_when_online(self, mode):
        mode._online = True
        tools = ["web_search", "code_exec", "file_ops"]
        allowed = mode.filter_tools(tools)
        assert allowed == tools

    def test_filter_tools_unknown_state(self, mode):
        mode._online = None
        allowed = mode.filter_tools(["web_search", "code_exec"])
        assert "web_search" in allowed

    def test_enqueue_operation(self, mode):
        from sovereign.modes.local_offline_mode import DeferredOperation
        op = DeferredOperation(
            operation_id="op-001",
            operation_type="memory_write",
            payload={"key": "val"},
        )
        mode.enqueue(op)
        assert len(mode.get_queue()) == 1

    def test_get_queue_empty(self, mode):
        assert mode.get_queue() == []

    @pytest.mark.asyncio
    async def test_flush_queue_empty(self, mode):
        async def executor(op):
            return True
        result = await mode.flush_queue(executor)
        assert result["flushed"] == 0

    @pytest.mark.asyncio
    async def test_flush_queue_success(self, mode):
        from sovereign.modes.local_offline_mode import DeferredOperation
        op = DeferredOperation(operation_id="op-1", operation_type="api_call", payload={})
        mode.enqueue(op)

        async def executor(op):
            return True

        result = await mode.flush_queue(executor)
        assert result["flushed"] == 1
        assert result["remaining"] == 0

    @pytest.mark.asyncio
    async def test_flush_queue_failure(self, mode):
        from sovereign.modes.local_offline_mode import DeferredOperation
        op = DeferredOperation(operation_id="op-2", operation_type="api_call", payload={})
        mode.enqueue(op)

        async def executor(op):
            return False

        result = await mode.flush_queue(executor)
        assert result["flushed"] == 0
        assert result["remaining"] == 1

    def test_export_state(self, mode):
        state = mode.export_state()
        assert state["mode"] == "local_offline"
        assert "queued_operations" in state

    def test_persistence_queue(self, tmp_path):
        from sovereign.modes.local_offline_mode import Local_offlineMode, DeferredOperation
        m1 = Local_offlineMode(data_dir=str(tmp_path))
        op = DeferredOperation(operation_id="p-1", operation_type="memory_write", payload={})
        m1.enqueue(op)
        m2 = Local_offlineMode(data_dir=str(tmp_path))
        assert len(m2.get_queue()) == 1


# ===========================================================================
# Swarm agent class attributes (no instantiation needed)
# ===========================================================================

class TestSwarmAgentAttributes:
    def test_special_agents_have_ids(self):
        from sovereign.swarm.special_agent import TrustScoringAgent, RiskEngineAgent
        assert TrustScoringAgent.agent_id == "trust_scorer"
        assert RiskEngineAgent.agent_id == "risk_engine"

    def test_worker_agent_model(self):
        from sovereign.swarm.worker_agent import WorkerAgent
        assert "sonnet" in WorkerAgent.model.lower() or "claude" in WorkerAgent.model.lower()

    def test_domain_chiefs_have_ids(self):
        from sovereign.swarm.domain_chiefs import ResearchChief, FinanceChief, ContentChief
        assert ResearchChief.agent_id == "research"
        assert FinanceChief.agent_id == "finance"
        assert ContentChief.agent_id == "content"

    def test_domain_chiefs_are_base_agent_subclasses(self):
        from sovereign.swarm.domain_chiefs import ResearchChief, FinanceChief, ContentChief
        from sovereign.swarm.base_agent import BaseAgent
        assert issubclass(ResearchChief, BaseAgent)
        assert issubclass(FinanceChief, BaseAgent)
        assert issubclass(ContentChief, BaseAgent)

    def test_special_agents_are_base_agent_subclasses(self):
        from sovereign.swarm.special_agent import TrustScoringAgent, RiskEngineAgent
        from sovereign.swarm.base_agent import BaseAgent
        assert issubclass(TrustScoringAgent, BaseAgent)
        assert issubclass(RiskEngineAgent, BaseAgent)

    def test_worker_agent_is_base_agent_subclass(self):
        from sovereign.swarm.worker_agent import WorkerAgent
        from sovereign.swarm.base_agent import BaseAgent
        assert issubclass(WorkerAgent, BaseAgent)
