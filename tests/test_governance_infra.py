"""
Tests for governance, infra, security, and privacy modules.

No real API key or network required.
"""
from __future__ import annotations

import asyncio

import pytest

# ---------------------------------------------------------------------------
# EscalationChain
# ---------------------------------------------------------------------------

class TestEscalationChain:
    def _chain(self, tmp_path):
        from sovereign.governance.escalation import EscalationChain
        return EscalationChain(persist_path=tmp_path / "esc.jsonl")

    def test_evaluate_auto(self, tmp_path):
        from sovereign.governance.escalation import EscalationLevel
        chain = self._chain(tmp_path)
        assert chain.evaluate("agent", "READ", 0.1) == EscalationLevel.AUTO

    def test_evaluate_operator_by_score(self, tmp_path):
        from sovereign.governance.escalation import EscalationLevel
        chain = self._chain(tmp_path)
        assert chain.evaluate("agent", "READ", 0.5) == EscalationLevel.OPERATOR

    def test_evaluate_admin(self, tmp_path):
        from sovereign.governance.escalation import EscalationLevel
        chain = self._chain(tmp_path)
        assert chain.evaluate("agent", "READ", 0.75) == EscalationLevel.ADMIN

    def test_evaluate_owner(self, tmp_path):
        from sovereign.governance.escalation import EscalationLevel
        chain = self._chain(tmp_path)
        assert chain.evaluate("agent", "READ", 0.95) == EscalationLevel.OWNER

    def test_evaluate_high_stakes_action_class(self, tmp_path):
        from sovereign.governance.escalation import EscalationLevel
        chain = self._chain(tmp_path)
        # LOW risk_score but EXECUTE action class → minimum OPERATOR
        level = chain.evaluate("agent", "EXECUTE", 0.1)
        assert level >= EscalationLevel.OPERATOR

    def test_create_and_pending(self, tmp_path):
        from sovereign.governance.escalation import EscalationLevel
        chain = self._chain(tmp_path)
        level = EscalationLevel.ADMIN
        event = chain.create_event("test trigger", "agent-1", "EXECUTE", 0.8, level)
        assert event.event_id
        assert event.level == EscalationLevel.ADMIN
        pending = chain.pending_events()
        assert len(pending) == 1
        assert pending[0].event_id == event.event_id

    def test_resolve(self, tmp_path):
        from sovereign.governance.escalation import EscalationLevel
        chain = self._chain(tmp_path)
        event = chain.create_event("t", "a", "EXECUTE", 0.8, EscalationLevel.ADMIN)
        result = chain.resolve(event.event_id, "approved by admin")
        assert result is True
        assert len(chain.pending_events()) == 0

    def test_resolve_unknown_returns_false(self, tmp_path):
        chain = self._chain(tmp_path)
        assert chain.resolve("non-existent-id", "n/a") is False

    def test_persistence_across_reload(self, tmp_path):
        from sovereign.governance.escalation import EscalationChain, EscalationLevel
        path = tmp_path / "esc.jsonl"
        chain = EscalationChain(persist_path=path)
        event = chain.create_event("trigger", "agent", "EXECUTE", 0.8, EscalationLevel.ADMIN)

        chain2 = EscalationChain(persist_path=path)
        pending = chain2.pending_events()
        assert len(pending) == 1
        assert pending[0].event_id == event.event_id


# ---------------------------------------------------------------------------
# SpendingLimitsEngine
# ---------------------------------------------------------------------------

class TestSpendingLimitsEngine:
    def _engine(self, tmp_path):
        from sovereign.governance.spending_limits import SpendingLimitsEngine
        return SpendingLimitsEngine(persist_path=tmp_path / "spending.jsonl")

    def test_check_within_limit(self, tmp_path):
        from sovereign.governance.spending_limits import SpendingCategory
        engine = self._engine(tmp_path)
        allowed, msg = engine.check(SpendingCategory.TOKENS, 1.0)
        assert allowed

    def test_record_and_daily_usage(self, tmp_path):
        from sovereign.governance.spending_limits import SpendingCategory
        engine = self._engine(tmp_path)
        engine.record_spend(SpendingCategory.TOKENS, 5.0, "test")
        usage = engine.daily_usage(SpendingCategory.TOKENS)
        assert usage == pytest.approx(5.0)

    def test_summary_returns_dict(self, tmp_path):
        engine = self._engine(tmp_path)
        s = engine.summary()
        assert isinstance(s, dict)

    def test_limit_exceeded(self, tmp_path):
        from sovereign.governance.spending_limits import SpendingCategory, SpendingLimit
        engine = self._engine(tmp_path)
        # Set a tiny daily cap
        engine.set_limit(SpendingLimit(
            category=SpendingCategory.TOKENS,
            daily_limit=0.01,
            monthly_limit=1.0,
            per_action_limit=10.0,
        ))
        engine.record_spend(SpendingCategory.TOKENS, 0.05, "burst")
        allowed, msg = engine.check(SpendingCategory.TOKENS, 0.01)
        assert not allowed
        assert "daily" in msg.lower() or "limit" in msg.lower()


# ---------------------------------------------------------------------------
# TokenBudgetEnforcer
# ---------------------------------------------------------------------------

class TestTokenBudgetEnforcer:
    def _enforcer(self, **kwargs):
        from sovereign.infra.token_budget_enforcer import TokenBudgetEnforcer
        return TokenBudgetEnforcer(**kwargs)

    def test_check_within_budget(self):
        e = self._enforcer(daily_token_limit=1_000_000)
        e.check(estimated_tokens=100)  # should not raise

    def test_budget_exceeded_raises(self):
        from sovereign.infra.token_budget_enforcer import TokenBudgetExceeded
        e = self._enforcer(daily_token_limit=500)
        e.record("agent", 400, 50)
        with pytest.raises(TokenBudgetExceeded):
            e.check(estimated_tokens=200)

    def test_record_accumulates(self):
        e = self._enforcer()
        e.record("agent-a", 1000, 200)
        e.record("agent-b", 500, 100)
        summary = e.daily_summary()
        # Total tokens = input+output: (1000+200) + (500+100) = 1800
        assert summary["tokens"] >= 1800

    def test_daily_summary_keys(self):
        e = self._enforcer()
        s = e.daily_summary()
        assert "tokens" in s
        assert "cost_usd" in s

    def test_monthly_summary_keys(self):
        e = self._enforcer()
        s = e.monthly_summary()
        assert "tokens" in s


# ---------------------------------------------------------------------------
# RiskScoringEngine
# ---------------------------------------------------------------------------

class TestRiskScoringEngine:
    def test_low_risk_read_action(self):
        from sovereign.governance.risk_scoring import RiskScoringEngine
        engine = RiskScoringEngine()
        score = engine.score("summarise meeting notes", "worker", "READ")
        assert score.overall >= 0.0
        assert score.overall <= 1.0
        assert score.is_low_risk()

    def test_high_risk_finance_execute(self):
        from sovereign.governance.risk_scoring import RiskScoringEngine
        engine = RiskScoringEngine()
        score = engine.score("transfer $500,000 to external account", "finance_agent", "EXECUTE")
        # Financial dimension should be elevated
        assert score.dimensions["financial"] > 0.3
        assert score.flags  # at least one risk flag

    def test_recommended_action_class_populated(self):
        from sovereign.governance.risk_scoring import RiskScoringEngine
        engine = RiskScoringEngine()
        score = engine.score("deploy to production", "devops_agent", "EXECUTE")
        assert isinstance(score.recommended_action_class, str)
        assert score.recommended_action_class  # non-empty string

    def test_flags_are_strings(self):
        from sovereign.governance.risk_scoring import RiskScoringEngine
        engine = RiskScoringEngine()
        score = engine.score("delete customer database", "dba_agent", "EXECUTE")
        assert all(isinstance(f, str) for f in score.flags)

    def test_dimensions_present(self):
        from sovereign.governance.risk_scoring import RiskScoringEngine
        engine = RiskScoringEngine()
        score = engine.score("send legal notice", "legal_agent", "DRAFT")
        for dim in ("financial", "operational", "reputational", "legal", "security", "strategic"):
            assert dim in score.dimensions


# ---------------------------------------------------------------------------
# NotificationService
# ---------------------------------------------------------------------------

class TestNotificationService:
    def test_send_and_unread(self):
        from sovereign.infra.notification_service import NotificationService, NotificationLevel
        svc = NotificationService()
        asyncio.get_event_loop().run_until_complete(
            svc.send(title="Test", body="Hello", level=NotificationLevel.INFO, source_agent="test")
        )
        unread = svc.unread()
        assert len(unread) >= 1
        assert any(n.title == "Test" for n in unread)

    def test_mark_read(self):
        from sovereign.infra.notification_service import NotificationService, NotificationLevel
        svc = NotificationService()
        asyncio.get_event_loop().run_until_complete(
            svc.send(title="Alert", body="body", level=NotificationLevel.WARNING, source_agent="a")
        )
        unread_before = len(svc.unread())
        n = svc.unread()[0]
        result = svc.mark_read(n.notification_id)
        assert result is True
        assert len(svc.unread()) == unread_before - 1

    def test_critical_count(self):
        from sovereign.infra.notification_service import NotificationService, NotificationLevel
        svc = NotificationService()
        asyncio.get_event_loop().run_until_complete(
            svc.send(title="Critical", body="CRITICAL", level=NotificationLevel.CRITICAL, source_agent="a")
        )
        assert svc.critical_count() >= 1

    def test_recent(self):
        from sovereign.infra.notification_service import NotificationService, NotificationLevel
        svc = NotificationService()
        for i in range(3):
            asyncio.get_event_loop().run_until_complete(
                svc.send(title=f"N{i}", body="b", level=NotificationLevel.INFO, source_agent="a")
            )
        assert len(svc.recent(2)) <= 2


# ---------------------------------------------------------------------------
# PrivacyMode
# ---------------------------------------------------------------------------

class TestPrivacyMode:
    def test_default_public(self):
        from sovereign.privacy.privacy_mode import PrivacyMode, PrivacyLevel
        pm = PrivacyMode()
        assert pm.level == PrivacyLevel.PUBLIC
        assert pm.is_cloud_allowed()

    def test_set_private(self):
        from sovereign.privacy.privacy_mode import PrivacyMode, PrivacyLevel
        pm = PrivacyMode()
        pm.set_level(PrivacyLevel.PRIVATE)
        assert pm.level == PrivacyLevel.PRIVATE

    def test_locked_disallows_cloud_for_sensitive(self):
        from sovereign.privacy.privacy_mode import PrivacyMode, PrivacyLevel
        pm = PrivacyMode()
        pm.set_level(PrivacyLevel.LOCKED)
        assert not pm.is_cloud_allowed(is_sensitive=True)

    def test_paranoid_disallows_all_cloud(self):
        from sovereign.privacy.privacy_mode import PrivacyMode, PrivacyLevel
        pm = PrivacyMode()
        pm.set_level(PrivacyLevel.PARANOID)
        assert not pm.is_cloud_allowed(is_sensitive=False)

    def test_public_allows_sensitive(self):
        from sovereign.privacy.privacy_mode import PrivacyMode
        pm = PrivacyMode()
        assert pm.is_cloud_allowed(is_sensitive=True)

    def test_status_dict(self):
        from sovereign.privacy.privacy_mode import PrivacyMode
        pm = PrivacyMode()
        s = pm.status()
        assert s["level"] == "PUBLIC"
        assert isinstance(s["cloud_allowed"], bool)


# ---------------------------------------------------------------------------
# SecureStorage
# ---------------------------------------------------------------------------

class TestSecureStorage:
    def test_store_and_retrieve(self, tmp_path):
        from sovereign.privacy.secure_storage import SecureStorage
        ss = SecureStorage(passphrase="testpass", data_dir=tmp_path)
        ss.store("api_key", "sk-secret-12345")
        value = ss.retrieve("api_key")
        assert value == "sk-secret-12345"

    def test_retrieve_missing_returns_none(self, tmp_path):
        from sovereign.privacy.secure_storage import SecureStorage
        ss = SecureStorage(passphrase="testpass", data_dir=tmp_path)
        assert ss.retrieve("nonexistent") is None

    def test_delete(self, tmp_path):
        from sovereign.privacy.secure_storage import SecureStorage
        ss = SecureStorage(passphrase="testpass", data_dir=tmp_path)
        ss.store("token", "abc")
        assert ss.delete("token") is True
        assert ss.retrieve("token") is None

    def test_list_names(self, tmp_path):
        from sovereign.privacy.secure_storage import SecureStorage
        ss = SecureStorage(passphrase="testpass", data_dir=tmp_path)
        ss.store("key_a", "v1")
        ss.store("key_b", "v2")
        names = ss.list_names()
        assert "key_a" in names
        assert "key_b" in names

    def test_wrong_passphrase_returns_garbage_or_none(self, tmp_path):
        from sovereign.privacy.secure_storage import SecureStorage
        ss = SecureStorage(passphrase="correct", data_dir=tmp_path)
        ss.store("secret", "mysecret")
        ss2 = SecureStorage(passphrase="wrong", data_dir=tmp_path)
        retrieved = ss2.retrieve("secret")
        # With XOR + different key, result should not equal the original
        assert retrieved != "mysecret"


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class TestScheduler:
    def test_schedule_job(self):
        from sovereign.infra.scheduler import Scheduler, ScheduleFrequency
        s = Scheduler()
        job = s.schedule(
            name="morning_brief",
            agent_id="ceo_agent",
            objective="write morning brief",
            frequency=ScheduleFrequency.DAILY,
        )
        assert job.job_id
        jobs = s.list_jobs()
        assert any(j.name == "morning_brief" for j in jobs)

    def test_unschedule_job(self):
        from sovereign.infra.scheduler import Scheduler, ScheduleFrequency
        s = Scheduler()
        job = s.schedule("j1", "agent", "do work", ScheduleFrequency.HOURLY)
        assert s.unschedule(job.job_id) is True
        assert s.unschedule("nonexistent") is False

    def test_due_jobs_returns_list(self):
        from sovereign.infra.scheduler import Scheduler, ScheduleFrequency
        s = Scheduler()
        s.schedule("weekly_review", "ceo_agent", "review week", ScheduleFrequency.WEEKLY)
        due = s.due_jobs()
        assert isinstance(due, list)

    def test_default_jobs_exist(self):
        from sovereign.infra.scheduler import Scheduler
        s = Scheduler()
        jobs = s.list_jobs()
        # Scheduler ships with built-in default jobs
        assert len(jobs) >= 1
