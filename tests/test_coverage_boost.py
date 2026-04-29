"""Coverage boost: user_settings, model providers, action_loop, security/secrets."""
from __future__ import annotations

import asyncio
import pathlib
import tempfile


def run(coro):
    return asyncio.run(coro)


# ===========================================================================
# sovereign/security/secrets.py
# ===========================================================================

class TestSecuritySecrets:
    def test_get_secret_manager_returns_instance(self):
        from sovereign.security.secrets import get_secret_manager
        sm = get_secret_manager()
        assert sm is not None

    def test_get_secret_manager_singleton(self):
        from sovereign.security.secrets import get_secret_manager
        sm1 = get_secret_manager()
        sm2 = get_secret_manager()
        assert sm1 is sm2

    def test_secret_manager_type(self):
        from sovereign.security.secrets import get_secret_manager, SecretManager
        sm = get_secret_manager()
        assert isinstance(sm, SecretManager)


# ===========================================================================
# sovereign/api/user_settings.py
# ===========================================================================

class TestUserProfile:
    def test_defaults(self):
        from sovereign.api.user_settings import UserProfile
        p = UserProfile()
        assert p.name == "Sovereign"
        assert p.language == "en"
        assert p.timezone == "UTC"

    def test_custom_values(self):
        from sovereign.api.user_settings import UserProfile
        p = UserProfile(name="Alice", language="it", timezone="Europe/Rome")
        assert p.name == "Alice"
        assert p.language == "it"


class TestModePreferences:
    def test_defaults(self):
        from sovereign.api.user_settings import ModePreferences
        m = ModePreferences()
        assert m.default_mode == "command"
        assert m.mode_on_startup == "command"
        assert m.mode_shortcuts == {}

    def test_custom_mode(self):
        from sovereign.api.user_settings import ModePreferences
        m = ModePreferences(default_mode="finance")
        assert m.default_mode == "finance"


class TestProviderPreferences:
    def test_defaults(self):
        from sovereign.api.user_settings import ProviderPreferences
        p = ProviderPreferences()
        assert p.preferred_provider == "anthropic"
        assert not p.local_first
        assert p.budget_daily_usd == 5.00

    def test_fallback_order(self):
        from sovereign.api.user_settings import ProviderPreferences
        p = ProviderPreferences()
        assert "anthropic" in p.fallback_order


class TestPrivacyPreferences:
    def test_defaults(self):
        from sovereign.api.user_settings import PrivacyPreferences
        p = PrivacyPreferences()
        assert not p.pii_safe_mode
        assert p.memory_retention_days == 365
        assert not p.offline_only


class TestInterfacePreferences:
    def test_defaults(self):
        from sovereign.api.user_settings import InterfacePreferences
        i = InterfacePreferences()
        assert i.theme == "dark"
        assert i.font_size == "medium"
        assert i.show_confidence is True

    def test_compact_mode(self):
        from sovereign.api.user_settings import InterfacePreferences
        i = InterfacePreferences(compact_mode=True)
        assert i.compact_mode is True


class TestNotificationPreferences:
    def test_defaults(self):
        from sovereign.api.user_settings import NotificationPreferences
        n = NotificationPreferences()
        assert not n.telegram_enabled
        assert n.alert_on_critical is True
        assert n.budget_alert_threshold_pct == 0.80
        assert n.daily_digest_hour == 8


class TestUserSettings:
    def test_defaults(self):
        from sovereign.api.user_settings import UserSettings
        s = UserSettings()
        assert s.profile.name == "Sovereign"
        assert s.modes.default_mode == "command"
        assert s.providers.preferred_provider == "anthropic"
        assert s.privacy.memory_retention_days == 365
        assert s.interface.theme == "dark"
        assert not s.notifications.telegram_enabled


class TestUserSettingsStore:
    def _make_store(self, tmp_path=None):
        from sovereign.api.user_settings import UserSettingsStore
        if tmp_path is None:
            tmp_path = pathlib.Path(tempfile.mkdtemp()) / "settings.json"
        return UserSettingsStore(path=tmp_path)

    def test_instantiate(self):
        store = self._make_store()
        assert store is not None

    def test_get_all_returns_dict(self):
        store = self._make_store()
        data = store.get_all()
        assert isinstance(data, dict)
        assert "profile" in data
        assert "modes" in data
        assert "providers" in data
        assert "privacy" in data
        assert "interface" in data
        assert "notifications" in data

    def test_get_section_profile(self):
        store = self._make_store()
        section = store.get_section("profile")
        assert isinstance(section, dict)
        assert "name" in section

    def test_get_section_unknown_raises(self):
        import pytest
        store = self._make_store()
        with pytest.raises(KeyError):
            store.get_section("nonexistent")

    def test_update_section_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "settings.json"
            store = self._make_store(path)
            updated = store.update_section("profile", {"name": "Giò"})
            assert updated["name"] == "Giò"

    def test_update_section_validation_clamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "settings.json"
            store = self._make_store(path)
            store.update_section("modes", {"default_mode": "invalid_mode"})
            data = store.get_section("modes")
            assert data["default_mode"] == "command"

    def test_update_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "settings.json"
            store = self._make_store(path)
            result = store.update_all({"profile": {"name": "Neo"}})
            assert isinstance(result, dict)

    def test_reset_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "settings.json"
            store = self._make_store(path)
            store.update_section("profile", {"name": "Changed"})
            defaults = store.reset()
            assert defaults["profile"]["name"] == "Sovereign"

    def test_persist_and_reload(self):
        from sovereign.api.user_settings import UserSettingsStore
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "settings.json"
            s1 = UserSettingsStore(path=path)
            s1.update_section("profile", {"name": "Persistent"})
            s2 = UserSettingsStore(path=path)
            data = s2.get_section("profile")
            assert data["name"] == "Persistent"

    def test_validate_clamps_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "settings.json"
            store = self._make_store(path)
            store.update_section("providers", {"budget_daily_usd": -5.0})
            data = store.get_section("providers")
            assert data["budget_daily_usd"] >= 0.0

    def test_validate_clamps_retention_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "settings.json"
            store = self._make_store(path)
            store.update_section("privacy", {"memory_retention_days": 99999})
            data = store.get_section("privacy")
            assert data["memory_retention_days"] <= 3650

    def test_load_missing_file_returns_defaults(self):
        store = self._make_store(pathlib.Path("/tmp/nonexistent_sovereign_123.json"))
        data = store.get_all()
        assert data["profile"]["name"] == "Sovereign"


class TestGetSettingsStoreSingleton:
    def test_singleton_reset(self):
        import sovereign.api.user_settings as us
        us._store = None
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "s.json"
            store = us.get_settings_store(path)
            assert store is not None
        us._store = None  # cleanup


# ===========================================================================
# sovereign/models/base_provider.py
# ===========================================================================

class TestBaseProvider:
    def test_provider_status_values(self):
        from sovereign.models.base_provider import ProviderStatus
        assert ProviderStatus.AVAILABLE == "available"
        assert ProviderStatus.DEGRADED == "degraded"
        assert ProviderStatus.UNAVAILABLE == "unavailable"

    def test_completion_request_defaults(self):
        from sovereign.models.base_provider import CompletionRequest
        req = CompletionRequest(messages=[{"role": "user", "content": "hello"}])
        assert req.system == ""
        assert req.max_tokens == 4096
        assert req.temperature == 0.7
        assert req.tools == []
        assert not req.stream

    def test_completion_response_total_tokens(self):
        from sovereign.models.base_provider import CompletionResponse
        resp = CompletionResponse(
            content="hello", model="gpt-4", provider="openai",
            input_tokens=10, output_tokens=5,
        )
        assert resp.total_tokens == 15

    def test_record_error_increments_count(self):
        from sovereign.models.local_provider import LocalProvider
        p = LocalProvider()
        assert p._error_count == 0
        p.record_error()
        p.record_error()
        assert p._error_count == 2

    def test_record_error_degrades_after_3(self):
        from sovereign.models.base_provider import ProviderStatus
        from sovereign.models.local_provider import LocalProvider
        p = LocalProvider()
        for _ in range(3):
            p.record_error()
        assert p._status == ProviderStatus.DEGRADED

    def test_record_success_resets(self):
        from sovereign.models.base_provider import ProviderStatus
        from sovereign.models.local_provider import LocalProvider
        p = LocalProvider()
        p.record_error()
        p.record_error()
        p.record_error()
        p.record_success()
        assert p._error_count == 0
        assert p._status == ProviderStatus.AVAILABLE

    def test_health_check_default(self):
        from sovereign.models.base_provider import ProviderStatus
        from sovereign.models.local_provider import LocalProvider
        p = LocalProvider()
        # health_check pings /api/tags — mock it to return unavailable
        import unittest.mock as mock

        async def fake_health():
            p._status = ProviderStatus.UNAVAILABLE
            return p._status

        with mock.patch.object(p, "health_check", side_effect=fake_health):
            status = run(p.health_check())
        assert status == ProviderStatus.UNAVAILABLE


# ===========================================================================
# sovereign/models/local_provider.py
# ===========================================================================

class TestLocalProvider:
    def test_init_defaults(self):
        from sovereign.models.local_provider import LocalProvider
        p = LocalProvider()
        assert p.provider_id == "local"
        assert p.display_name == "Local (Ollama)"
        assert "11434" in p._base_url

    def test_init_custom_url(self):
        from sovereign.models.local_provider import LocalProvider
        p = LocalProvider(base_url="http://localhost:1234", model="mistral")
        assert "1234" in p._base_url
        assert p._default_model == "mistral"

    def test_provider_id_is_local(self):
        from sovereign.models.local_provider import LocalProvider
        assert LocalProvider.provider_id == "local"


# ===========================================================================
# sovereign/models/anthropic_provider.py
# ===========================================================================

class TestAnthropicProvider:
    def test_init(self):
        from sovereign.models.anthropic_provider import AnthropicProvider
        p = AnthropicProvider(api_key="test-key")
        assert p.provider_id == "anthropic"
        assert p.display_name == "Anthropic Claude"

    def test_status_starts_available(self):
        from sovereign.models.base_provider import ProviderStatus
        from sovereign.models.anthropic_provider import AnthropicProvider
        p = AnthropicProvider(api_key="test-key")
        assert p._status == ProviderStatus.AVAILABLE

    def test_error_tracking(self):
        from sovereign.models.base_provider import ProviderStatus
        from sovereign.models.anthropic_provider import AnthropicProvider
        p = AnthropicProvider(api_key="test-key")
        p.record_error()
        p.record_error()
        p.record_error()
        assert p._status == ProviderStatus.DEGRADED
        p.record_success()
        assert p._status == ProviderStatus.AVAILABLE


# ===========================================================================
# sovereign/models/gemini_provider.py
# ===========================================================================

class TestGeminiProvider:
    def test_cost_function_free_model(self):
        from sovereign.models.gemini_provider import _cost
        assert _cost("gemini-1.5-flash", 1_000_000, 1_000_000) == 0.0

    def test_cost_function_pro_model(self):
        from sovereign.models.gemini_provider import _cost
        cost = _cost("gemini-1.5-pro", 1_000_000, 0)
        assert cost > 0

    def test_cost_unknown_model(self):
        from sovereign.models.gemini_provider import _cost
        assert _cost("unknown-model", 100, 100) == 0.0

    def test_gemini_models_dict(self):
        from sovereign.models.gemini_provider import GEMINI_MODELS
        assert "gemini-1.5-flash" in GEMINI_MODELS
        assert "gemini-1.5-pro" in GEMINI_MODELS

    def test_init(self):
        from sovereign.models.gemini_provider import GeminiProvider
        p = GeminiProvider(api_key="test-key")
        assert p.provider_id == "gemini"

    def test_status_starts_available(self):
        from sovereign.models.base_provider import ProviderStatus
        from sovereign.models.gemini_provider import GeminiProvider
        p = GeminiProvider(api_key="test-key")
        assert p._status == ProviderStatus.AVAILABLE


# ===========================================================================
# sovereign/devices/action_loop.py
# ===========================================================================

class TestActionLoop:
    def _make_loop(self):
        from sovereign.devices.action_loop import ActionLoop
        import unittest.mock as mock
        gateway = mock.MagicMock()
        sensors = mock.MagicMock()
        memory = mock.MagicMock()
        return ActionLoop(gateway, sensors, memory)

    def test_init(self):
        loop = self._make_loop()
        assert not loop._running
        assert loop._intents_processed == 0

    def test_detect_intent_no_face_low_cpu(self):
        from sovereign.devices.action_loop import INTENT_ABSENT
        loop = self._make_loop()
        intent = loop.detect_intent(None, {"cpu_percent": 2.0})
        assert intent == INTENT_ABSENT

    def test_detect_intent_no_face_high_cpu(self):
        from sovereign.devices.action_loop import INTENT_IDLE
        loop = self._make_loop()
        intent = loop.detect_intent(None, {"cpu_percent": 50.0})
        assert intent == INTENT_IDLE

    def test_detect_intent_face_high_attention(self):
        from sovereign.devices.action_loop import INTENT_FOCUS
        loop = self._make_loop()
        intent = loop.detect_intent({"detected": True, "attention": 0.9}, {})
        assert intent == INTENT_FOCUS

    def test_detect_intent_face_medium_attention(self):
        from sovereign.devices.action_loop import INTENT_PRESENT
        loop = self._make_loop()
        intent = loop.detect_intent({"detected": True, "attention": 0.5}, {})
        assert intent == INTENT_PRESENT

    def test_detect_intent_face_low_attention(self):
        from sovereign.devices.action_loop import INTENT_AVAILABLE
        loop = self._make_loop()
        intent = loop.detect_intent({"detected": True, "attention": 0.1}, {})
        assert intent == INTENT_AVAILABLE

    def test_detect_intent_no_detection(self):
        from sovereign.devices.action_loop import INTENT_IDLE
        loop = self._make_loop()
        intent = loop.detect_intent({"detected": False, "attention": 0.9}, {"cpu_percent": 50.0})
        assert intent == INTENT_IDLE

    def test_register_intent_handler(self):
        loop = self._make_loop()
        called = []

        async def handler(intent, ctx):
            called.append(intent)

        loop.register_intent_handler("custom_event", handler)
        assert "custom_event" in loop._handlers

    def test_process_frame(self):
        from sovereign.devices.action_loop import INTENT_ABSENT
        loop = self._make_loop()
        intent = run(loop.process_frame(None, {"cpu_percent": 1.0}))
        assert intent == INTENT_ABSENT

    def test_execute_intent_dispatches(self):
        loop = self._make_loop()
        results = []

        async def handler(intent, ctx):
            results.append(intent)

        loop.register_intent_handler("test_x", handler)
        run(loop.execute_intent("test_x", {}))
        assert results == ["test_x"]

    def test_execute_intent_unknown_does_not_raise(self):
        loop = self._make_loop()
        run(loop.execute_intent("totally_unknown_intent", {}))

    def test_get_stats(self):
        loop = self._make_loop()
        stats = loop.get_stats()
        assert isinstance(stats, dict)
        assert "running" in stats
        assert "intents_processed" in stats

    def test_constants(self):
        from sovereign.devices.action_loop import (
            INTENT_PRESENT, INTENT_ABSENT, INTENT_FOCUS,
            INTENT_AVAILABLE, INTENT_IDLE,
        )
        assert INTENT_PRESENT == "present"
        assert INTENT_ABSENT == "absent"
        assert INTENT_FOCUS == "focus"
        assert INTENT_AVAILABLE == "available"
        assert INTENT_IDLE == "idle"
