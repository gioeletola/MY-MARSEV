"""Tests for extended modes, Telegram integration, and superpower_files."""
from __future__ import annotations
import pytest


# ── Extended Modes ────────────────────────────────────────────────────────────

def test_all_17_modes_in_registry():
    from sovereign.modes import MODES
    expected = {
        "command", "business", "personal", "finance", "study", "travel",
        "research", "builder", "local_offline", "survival", "caveman",
        "founder", "war", "prestige", "silent", "recovery", "emergency",
    }
    assert expected == set(MODES.keys())


def test_caveman_mode_attributes():
    from sovereign.modes.caveman_mode import CavemanMode
    m = CavemanMode()
    assert m.name == "caveman"
    assert m.offline_capable is True
    assert m.max_tokens() == 512
    assert m.preferred_model == "claude-haiku-4-5-20251001"
    overrides = m.routing_overrides()
    assert overrides["budget_limit_usd"] <= 0.01
    assert "[CAVEMAN MODE]" in m.system_prompt_suffix()
    assert m.select_model_for_provider("openai") == "gpt-4o-mini"
    assert m.select_model_for_provider("qwen") == "qwen2.5:7b"


def test_caveman_cheap_model_chain():
    from sovereign.modes.caveman_mode import CavemanMode
    m = CavemanMode()
    chain = m.CHEAP_MODEL_CHAIN
    providers = [p for p, _ in chain]
    assert "anthropic" in providers
    assert "qwen" in providers
    assert "local" in providers


def test_founder_mode_attributes():
    from sovereign.modes.founder_mode import FounderMode
    m = FounderMode()
    assert m.name == "founder"
    assert m.escalation_threshold >= 0.7
    assert len(m.ACTIVE_AGENTS) >= 5


def test_war_mode_uses_opus():
    from sovereign.modes.war_mode import WarMode
    m = WarMode()
    assert "opus" in m.preferred_model
    assert m.escalation_threshold <= 0.35


def test_prestige_mode_uses_opus():
    from sovereign.modes.prestige_mode import PrestigeMode
    m = PrestigeMode()
    assert "opus" in m.preferred_model
    assert m.MIN_CONFIDENCE >= 0.9


def test_silent_mode_offline_capable():
    from sovereign.modes.silent_mode import SilentMode
    m = SilentMode()
    assert m.offline_capable is True
    assert m.NO_LOGGING is True
    assert m.NO_CLOUD is True


def test_recovery_mode_attributes():
    from sovereign.modes.recovery_mode import RecoveryMode
    m = RecoveryMode()
    assert m.name == "recovery"
    assert len(m.ACTIVE_AGENTS) >= 5


def test_emergency_mode_lowest_threshold():
    from sovereign.modes.emergency_mode import EmergencyMode
    m = EmergencyMode()
    assert m.escalation_threshold <= 0.15
    assert m.offline_capable is True
    assert m.BYPASS_APPROVAL_FOR_SAFETY is True


def test_mode_get_by_name():
    from sovereign.modes.base_mode import BaseMode
    mode = BaseMode.get_mode("war")
    assert mode.name == "war"


def test_mode_get_unknown_raises():
    from sovereign.modes.base_mode import BaseMode
    with pytest.raises(ValueError, match="Unknown mode"):
        BaseMode.get_mode("nonexistent_xyz_mode")


def test_mode_to_dict():
    from sovereign.modes import MODES
    for name, mode in MODES.items():
        d = mode.to_dict()
        assert d["name"] == name
        assert "escalation_threshold" in d
        assert "preferred_model" in d


# ── SuperpowerFiles ───────────────────────────────────────────────────────────

def test_superpower_loader_loads_all_packs():
    from sovereign.superpower_files.loader import SuperpowerLoader
    loader = SuperpowerLoader()
    packs = loader.list_packs()
    assert len(packs) == 8
    expected = {"negotiation", "fundraising", "product", "growth",
                "legal_basics", "mental_models", "financial_iq", "leadership"}
    assert set(packs) == expected


def test_superpower_loader_render():
    from sovereign.superpower_files.loader import SuperpowerLoader
    loader = SuperpowerLoader()
    text = loader.render("negotiation")
    assert "NEGOTIATION" in text.upper()
    assert len(text) > 100


def test_superpower_loader_inject():
    from sovereign.superpower_files.loader import SuperpowerLoader
    loader = SuperpowerLoader()
    result = loader.inject(["mental_models"], "You are an agent.")
    assert "You are an agent." in result
    assert "MENTAL MODEL" in result.upper()


def test_superpower_loader_get_pack():
    from sovereign.superpower_files.loader import SuperpowerLoader
    loader = SuperpowerLoader()
    pack = loader.get("fundraising")
    assert pack is not None
    assert "sections" in pack


def test_superpower_loader_missing_pack():
    from sovereign.superpower_files.loader import SuperpowerLoader
    loader = SuperpowerLoader()
    assert loader.get("nonexistent_pack_xyz") is None
    assert loader.render("nonexistent_pack_xyz") == ""


def test_superpower_pack_sections_not_empty():
    from sovereign.superpower_files import negotiation, fundraising, mental_models
    from sovereign.superpower_files import financial_iq, leadership, product, growth, legal_basics
    for mod in [negotiation, fundraising, mental_models, financial_iq, leadership, product, growth, legal_basics]:
        pack = mod.PACK
        assert "title" in pack
        assert "sections" in pack
        assert len(pack["sections"]) >= 3


# ── TelegramIntegration ───────────────────────────────────────────────────────

def test_telegram_integration_imports():
    from sovereign.integrations.telegram_integration import TelegramIntegration
    t = TelegramIntegration()
    assert t.integration_id == "telegram"


def test_telegram_connect_without_token():
    from sovereign.integrations.telegram_integration import TelegramIntegration
    from sovereign.integrations.base_integration import IntegrationConfig, IntegrationStatus
    t = TelegramIntegration()
    config = IntegrationConfig(integration_id="telegram", name="telegram",
                               credentials={}, settings={}, enabled=True)
    result = t.connect(config)
    assert result is False
    assert t._status == IntegrationStatus.DISCONNECTED


def test_telegram_message_split_long():
    from sovereign.integrations.telegram_integration import TelegramIntegration
    long_text = "x" * 5000
    chunks = TelegramIntegration._split(long_text)
    assert len(chunks) == 2
    assert all(len(c) <= 4096 for c in chunks)


def test_telegram_message_split_short():
    from sovereign.integrations.telegram_integration import TelegramIntegration
    chunks = TelegramIntegration._split("hello world")
    assert chunks == ["hello world"]


def test_telegram_register_handlers():
    from sovereign.integrations.telegram_integration import TelegramIntegration
    t = TelegramIntegration()

    async def handler(msg): pass

    t.on_command("/status", handler)
    assert len(t._handlers) == 1
    assert t._handlers[0][0] == "status"


def test_telegram_fallback_handler():
    from sovereign.integrations.telegram_integration import TelegramIntegration
    t = TelegramIntegration()

    async def fallback(msg): pass

    t.on_message(fallback)
    assert t._fallback_handler is fallback


@pytest.mark.asyncio
async def test_telegram_send_without_connection():
    from sovereign.integrations.telegram_integration import TelegramIntegration
    t = TelegramIntegration()
    result = await t.send_message(12345, "hello")
    assert result is False


@pytest.mark.asyncio
async def test_telegram_dispatch_ignores_unauthorised():
    from sovereign.integrations.telegram_integration import TelegramIntegration
    t = TelegramIntegration()
    t._allowed_ids = {99999}
    received = []

    async def handler(msg): received.append(msg)

    t.on_message(handler)
    update = {"message": {"chat": {"id": 12345}, "text": "hi", "message_id": 1, "from": {}, "date": 0}}
    await t._dispatch(update)
    assert len(received) == 0


@pytest.mark.asyncio
async def test_telegram_dispatch_routes_command():
    from sovereign.integrations.telegram_integration import TelegramIntegration
    t = TelegramIntegration()
    received = []

    async def status_handler(msg): received.append(msg)

    t.on_command("/status", status_handler)
    update = {"message": {"chat": {"id": 123}, "text": "/status", "message_id": 1, "from": {}, "date": 0}}
    await t._dispatch(update)
    assert len(received) == 1
    assert received[0]["command"] == "status"
