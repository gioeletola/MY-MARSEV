"""Tests for sovereign/models/ — provider layer, fallback chain, privacy router, caveman mode."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── ModelCapabilityRegistry ──────────────────────────────────────────────────

def test_capability_registry_list_all():
    from sovereign.models.model_capability_registry import ModelCapabilityRegistry
    reg = ModelCapabilityRegistry()
    all_models = reg.list_all()
    assert len(all_models) >= 5


def test_capability_registry_get_known():
    from sovereign.models.model_capability_registry import ModelCapabilityRegistry
    reg = ModelCapabilityRegistry()
    cap = reg.get("claude-sonnet-4-6")
    assert cap is not None
    assert cap.provider == "anthropic"
    assert cap.context_window >= 100_000


def test_capability_registry_get_missing():
    from sovereign.models.model_capability_registry import ModelCapabilityRegistry
    reg = ModelCapabilityRegistry()
    assert reg.get("nonexistent-model-xyz") is None


def test_capability_registry_privacy_safe():
    from sovereign.models.model_capability_registry import ModelCapabilityRegistry
    reg = ModelCapabilityRegistry()
    safe = reg.privacy_safe_models()
    assert len(safe) >= 1
    for m in safe:
        assert m.privacy_safe is True


def test_capability_registry_by_provider():
    from sovereign.models.model_capability_registry import ModelCapabilityRegistry
    reg = ModelCapabilityRegistry()
    anthropic_models = reg.by_provider("anthropic")
    assert len(anthropic_models) >= 3


def test_capability_registry_cheapest_for_context():
    from sovereign.models.model_capability_registry import ModelCapabilityRegistry
    reg = ModelCapabilityRegistry()
    cheapest = reg.cheapest_for_context(100_000)
    assert cheapest is not None
    assert cheapest.context_window >= 100_000


# ── FallbackChain ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_chain_uses_primary():
    from sovereign.models.fallback_chain import FallbackChain
    from sovereign.models.base_provider import CompletionRequest, CompletionResponse, ProviderStatus

    mock_provider = MagicMock()
    mock_provider.provider_id = "mock_primary"
    mock_provider._status = ProviderStatus.AVAILABLE
    mock_provider.health_check = AsyncMock(return_value=ProviderStatus.AVAILABLE)
    mock_provider.complete = AsyncMock(return_value=CompletionResponse(
        content="hello", model="test", provider="mock_primary"
    ))

    chain = FallbackChain([mock_provider])
    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    resp = await chain.complete(req)
    assert resp.content == "hello"
    assert resp.provider == "mock_primary"


@pytest.mark.asyncio
async def test_fallback_chain_falls_through_on_error():
    from sovereign.models.fallback_chain import FallbackChain
    from sovereign.models.base_provider import CompletionRequest, CompletionResponse, ProviderStatus

    failing = MagicMock()
    failing.provider_id = "failing"
    failing._status = ProviderStatus.AVAILABLE
    failing.health_check = AsyncMock(return_value=ProviderStatus.AVAILABLE)
    failing.complete = AsyncMock(side_effect=RuntimeError("API down"))

    backup = MagicMock()
    backup.provider_id = "backup"
    backup._status = ProviderStatus.AVAILABLE
    backup.health_check = AsyncMock(return_value=ProviderStatus.AVAILABLE)
    backup.complete = AsyncMock(return_value=CompletionResponse(
        content="fallback response", model="test", provider="backup"
    ))

    chain = FallbackChain([failing, backup])
    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    resp = await chain.complete(req)
    assert resp.content == "fallback response"
    assert resp.provider == "backup"


@pytest.mark.asyncio
async def test_fallback_chain_skips_unavailable():
    from sovereign.models.fallback_chain import FallbackChain
    from sovereign.models.base_provider import CompletionRequest, CompletionResponse, ProviderStatus

    unavailable = MagicMock()
    unavailable.provider_id = "unavailable"
    unavailable._status = ProviderStatus.UNAVAILABLE
    unavailable.health_check = AsyncMock(return_value=ProviderStatus.UNAVAILABLE)

    available = MagicMock()
    available.provider_id = "available"
    available._status = ProviderStatus.AVAILABLE
    available.health_check = AsyncMock(return_value=ProviderStatus.AVAILABLE)
    available.complete = AsyncMock(return_value=CompletionResponse(
        content="ok", model="t", provider="available"
    ))

    chain = FallbackChain([unavailable, available])
    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    resp = await chain.complete(req)
    assert resp.provider == "available"


@pytest.mark.asyncio
async def test_fallback_chain_all_fail_raises():
    from sovereign.models.fallback_chain import FallbackChain
    from sovereign.models.base_provider import CompletionRequest, ProviderStatus

    p = MagicMock()
    p.provider_id = "p"
    p._status = ProviderStatus.AVAILABLE
    p.health_check = AsyncMock(return_value=ProviderStatus.AVAILABLE)
    p.complete = AsyncMock(side_effect=RuntimeError("boom"))

    chain = FallbackChain([p])
    req = CompletionRequest(messages=[{"role": "user", "content": "hi"}])
    with pytest.raises(RuntimeError, match="exhausted"):
        await chain.complete(req)


# ── PrivacyRouter ─────────────────────────────────────────────────────────────

def test_privacy_router_sensitivity_check_positive():
    from sovereign.models.privacy_router import PrivacyRouter
    from unittest.mock import MagicMock
    pr = PrivacyRouter(cloud_provider=MagicMock())
    assert pr.sensitivity_check("my api_key is abc123") is True


def test_privacy_router_sensitivity_check_negative():
    from sovereign.models.privacy_router import PrivacyRouter
    from unittest.mock import MagicMock
    pr = PrivacyRouter(cloud_provider=MagicMock())
    assert pr.sensitivity_check("analyse my cashflow for this month") is False


# ── CavemanMode / TokenBudget ─────────────────────────────────────────────────

def test_caveman_usage_report(tmp_path):
    from sovereign.models.caveman_mode import CavemanMode, TokenBudget
    from unittest.mock import MagicMock
    import sovereign.models.caveman_mode as cm_module
    cm_module._DATA_FILE = tmp_path / "budget.json"

    provider = MagicMock()
    budget = TokenBudget(monthly_input_limit=1_000_000, daily_input_limit=100_000)
    cm = CavemanMode(provider, budget)
    report = cm.usage_report()
    assert "day" in report
    assert "month" in report
    assert report["day"]["limit"] == 100_000


# ── IntentRadar ───────────────────────────────────────────────────────────────

def test_intent_radar_finance():
    from sovereign.perception.intent_radar import IntentRadar
    radar = IntentRadar()
    result = radar.classify("analyse my cashflow for this month")
    assert result.intent == "finance_query"
    assert result.mode_hint == "finance"


def test_intent_radar_engineering():
    from sovereign.perception.intent_radar import IntentRadar
    radar = IntentRadar()
    result = radar.classify("debug and fix this code")
    assert result.intent == "engineering_task"


def test_intent_radar_general():
    from sovereign.perception.intent_radar import IntentRadar
    radar = IntentRadar()
    result = radar.classify("hello there")
    assert result.intent == "general"
    assert 0.0 <= result.confidence <= 1.0


# ── SuggestionEngine ─────────────────────────────────────────────────────────

def test_suggestion_engine_evaluate():
    from sovereign.proactive.suggestion_engine import SuggestionEngine
    engine = SuggestionEngine()
    snap = {"financial": {"monthly_cashflow": 100}}
    suggestions = engine.evaluate(snap)
    assert isinstance(suggestions, list)
    ids = [s.suggestion_id for s in suggestions]
    assert "low_cashflow" in ids


def test_suggestion_engine_dismiss():
    from sovereign.proactive.suggestion_engine import SuggestionEngine
    engine = SuggestionEngine()
    snap = {"financial": {"monthly_cashflow": 100}}
    engine.evaluate(snap)
    engine.dismiss("low_cashflow")
    remaining = engine.evaluate(snap)
    assert all(s.suggestion_id != "low_cashflow" for s in remaining)


# ── GoalMonitor ───────────────────────────────────────────────────────────────

def test_goal_monitor_add_and_progress(tmp_path):
    from sovereign.proactive.goal_monitor import GoalMonitor, Goal
    import sovereign.proactive.goal_monitor as gm_module
    gm_module._DATA_FILE = tmp_path / "goals.json"

    monitor = GoalMonitor()
    goal = Goal(goal_id="g1", title="Save $10k", description="Savings goal",
                target_value=10000.0, unit="USD")
    monitor.add(goal)
    updated = monitor.update_progress("g1", 5000.0)
    assert updated is not None
    assert updated.progress_pct == 50.0
    assert len(monitor.active_goals()) == 1


def test_goal_monitor_completion(tmp_path):
    from sovereign.proactive.goal_monitor import GoalMonitor, Goal, GoalStatus
    import sovereign.proactive.goal_monitor as gm_module
    gm_module._DATA_FILE = tmp_path / "goals.json"

    monitor = GoalMonitor()
    goal = Goal(goal_id="g2", title="Read 12 books", description="", target_value=12.0)
    monitor.add(goal)
    monitor.update_progress("g2", 12.0)
    g = monitor._goals["g2"]
    assert g.status == GoalStatus.COMPLETED


# ── ScenarioEngine ────────────────────────────────────────────────────────────

def test_scenario_engine_create_and_get():
    from sovereign.forecasting.scenario_engine import ScenarioEngine, Scenario
    engine = ScenarioEngine()
    s = Scenario(scenario_id="s1", name="Base case", description="Normal growth",
                 probability=0.6, impact="medium")
    engine.create(s)
    result = engine.get("s1")
    assert result is not None
    assert result.probability == 0.6


def test_scenario_engine_compare():
    from sovereign.forecasting.scenario_engine import ScenarioEngine, Scenario
    engine = ScenarioEngine()
    engine.create(Scenario("base", "Base", "Normal", probability=0.5, impact="medium"))
    engine.create(Scenario("bull", "Bull case", "Strong growth", probability=0.8, impact="high"))
    comp = engine.compare("base", ["bull"])
    assert comp is not None
    assert comp.recommended in ("base", "bull")


# ── SignalFusion ──────────────────────────────────────────────────────────────

def test_signal_fusion_weighted_mean():
    from sovereign.forecasting.signal_fusion import SignalFusion, Signal
    fusion = SignalFusion()
    signals = [
        Signal("s1", "agent_a", value=0.8, weight=2.0, confidence=0.9),
        Signal("s2", "agent_b", value=0.4, weight=1.0, confidence=0.7),
    ]
    result = fusion.fuse("market_outlook", signals)
    assert 0.0 <= result.fused_value <= 1.0
    assert result.fused_confidence > 0.0
    assert result.interpretation != ""


# ── PrivacyMode ───────────────────────────────────────────────────────────────

def test_privacy_mode_levels():
    from sovereign.privacy.privacy_mode import PrivacyMode, PrivacyLevel
    pm = PrivacyMode()
    assert pm.level == PrivacyLevel.PUBLIC
    assert pm.is_cloud_allowed() is True

    pm.set_level(PrivacyLevel.LOCKED)
    assert pm.is_cloud_allowed() is False
    assert pm.is_logging_allowed() is False


def test_privacy_mode_paranoid():
    from sovereign.privacy.privacy_mode import PrivacyMode, PrivacyLevel
    pm = PrivacyMode()
    pm.set_level(PrivacyLevel.PARANOID)
    assert pm.is_external_domain_allowed("api.anthropic.com") is False


# ── SecureStorage ─────────────────────────────────────────────────────────────

def test_secure_storage_store_retrieve(tmp_path):
    from sovereign.privacy.secure_storage import SecureStorage
    storage = SecureStorage(passphrase="test_key", data_dir=tmp_path / "secure")
    storage.store("my_secret", "super_secret_value")
    retrieved = storage.retrieve("my_secret")
    assert retrieved == "super_secret_value"


def test_secure_storage_delete(tmp_path):
    from sovereign.privacy.secure_storage import SecureStorage
    storage = SecureStorage(passphrase="test_key", data_dir=tmp_path / "secure")
    storage.store("to_delete", "value")
    assert storage.delete("to_delete") is True
    assert storage.retrieve("to_delete") is None


def test_secure_storage_list(tmp_path):
    from sovereign.privacy.secure_storage import SecureStorage
    storage = SecureStorage(passphrase="test_key", data_dir=tmp_path / "secure")
    storage.store("k1", "v1")
    storage.store("k2", "v2")
    names = storage.list_names()
    assert "k1" in names
    assert "k2" in names


# ── PromotionRules ────────────────────────────────────────────────────────────

def test_promotion_sandbox_to_shadow():
    from sovereign.expansion.promotion_rules import PromotionRules, AgentLifecycleStage
    rules = PromotionRules()
    rules.register("my_agent")
    rules.update_eval("my_agent", 0.85)
    new_stage = rules.promote("my_agent")
    assert new_stage == AgentLifecycleStage.SHADOW


def test_promotion_blocked_insufficient_score():
    from sovereign.expansion.promotion_rules import PromotionRules
    rules = PromotionRules()
    rules.register("weak_agent")
    rules.update_eval("weak_agent", 0.50)
    result = rules.promote("weak_agent")
    assert result is None


def test_promotion_rollback():
    from sovereign.expansion.promotion_rules import PromotionRules, AgentLifecycleStage
    rules = PromotionRules()
    rules.register("agent_r")
    rules.update_eval("agent_r", 0.90)
    rules.promote("agent_r")
    assert rules.rollback("agent_r") is True
    assert rules._records["agent_r"].stage == AgentLifecycleStage.SANDBOX


# ── CapabilityGapDetector ─────────────────────────────────────────────────────

def test_gap_detector_records_failure():
    from sovereign.expansion.capability_gap_detector import CapabilityGapDetector
    detector = CapabilityGapDetector()
    detector.record_failure("analyse satellite imagery data", "no_agent", "no handler")
    gaps = detector.all_gaps()
    assert len(gaps) >= 1


def test_gap_detector_top_gaps():
    from sovereign.expansion.capability_gap_detector import CapabilityGapDetector
    detector = CapabilityGapDetector()
    for _ in range(5):
        detector.record_failure("process audio transcripts", "some_agent", "err")
    detector.record_failure("build a dashboard", "other_agent", "err")
    top = detector.top_gaps(1)
    assert top[0].frequency >= 5


# ── TokenBudgetEnforcer ───────────────────────────────────────────────────────

def test_token_budget_enforcer_check_passes(tmp_path):
    from sovereign.infra.token_budget_enforcer import TokenBudgetEnforcer
    import sovereign.infra.token_budget_enforcer as tbe_mod
    tbe_mod._DATA_FILE = tmp_path / "budget.json"
    enforcer = TokenBudgetEnforcer(daily_token_limit=1_000_000)
    enforcer.check(estimated_tokens=100)


def test_token_budget_enforcer_blocks_over_limit(tmp_path):
    from sovereign.infra.token_budget_enforcer import TokenBudgetEnforcer, TokenBudgetExceeded
    import sovereign.infra.token_budget_enforcer as tbe_mod
    tbe_mod._DATA_FILE = tmp_path / "budget.json"
    enforcer = TokenBudgetEnforcer(daily_token_limit=100)
    with pytest.raises(TokenBudgetExceeded):
        enforcer.check(estimated_tokens=200)


def test_token_budget_enforcer_record_and_summary(tmp_path):
    from sovereign.infra.token_budget_enforcer import TokenBudgetEnforcer
    import sovereign.infra.token_budget_enforcer as tbe_mod
    tbe_mod._DATA_FILE = tmp_path / "budget.json"
    enforcer = TokenBudgetEnforcer()
    enforcer.record("ceo_agent", input_tokens=500, output_tokens=200, cost_usd=0.01)
    summary = enforcer.daily_summary()
    assert summary["tokens"] == 700
    assert summary["calls"] == 1


# ── ConfidenceTracker ─────────────────────────────────────────────────────────

def test_confidence_tracker_record_and_resolve(tmp_path):
    from sovereign.forecasting.confidence_tracker import ConfidenceTracker
    import sovereign.forecasting.confidence_tracker as ct_mod
    ct_mod._DATA_FILE = tmp_path / "ct.json"

    tracker = ConfidenceTracker()
    rec = tracker.record("cashflow_analyst", "Revenue up 10% next quarter", 0.75)
    tracker.resolve(rec.record_id, "Revenue up 8%", correct=True)
    calib = tracker.calibration("cashflow_analyst")
    assert calib["accuracy"] == 1.0
    assert calib["count"] == 1
