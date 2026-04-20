"""
User settings store — persists user profile, preferences, and configuration.

All settings are stored as a single JSON file under data/memory/user_settings.json.
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/memory/user_settings.json")

_VALID_MODES = [
    "command", "business", "personal", "finance", "study", "travel",
    "research", "builder", "local_offline", "survival",
    "founder", "war", "prestige", "silent", "recovery", "emergency",
]

_VALID_PROVIDERS = ["anthropic", "openai", "gemini", "qwen", "perplexity", "local"]

_VALID_THEMES = ["dark", "dim", "light"]
_VALID_FONT_SIZES = ["small", "medium", "large"]
_VALID_LANGUAGES = ["en", "it", "es", "fr", "de", "pt", "zh", "ja"]


@dataclass
class UserProfile:
    name: str = "Sovereign"
    bio: str = ""
    timezone: str = "UTC"
    language: str = "en"
    avatar_url: str = ""


@dataclass
class ModePreferences:
    default_mode: str = "command"
    mode_on_startup: str = "command"
    mode_shortcuts: dict[str, str] = field(default_factory=dict)


@dataclass
class ProviderPreferences:
    preferred_provider: str = "anthropic"
    fallback_order: list[str] = field(default_factory=lambda: [
        "anthropic", "openai", "qwen", "gemini", "local"
    ])
    local_first: bool = False
    qwen_backend: str = "ollama"       # "ollama" | "vllm"
    qwen_base_url: str = ""
    offline_default_model: str = "qwen2.5:7b"
    max_cost_per_request_usd: float = 0.50
    budget_daily_usd: float = 5.00


@dataclass
class PrivacyPreferences:
    pii_safe_mode: bool = False        # force all data to local/qwen
    memory_retention_days: int = 365
    share_usage_analytics: bool = False
    redact_logs: bool = False
    offline_only: bool = False


@dataclass
class InterfacePreferences:
    theme: str = "dark"
    font_size: str = "medium"
    show_confidence: bool = True
    show_agent_trace: bool = True
    show_token_usage: bool = True
    compact_mode: bool = False
    sidebar_collapsed: bool = False
    default_panel: str = "chat"        # "chat" | "dashboard" | "finance"


@dataclass
class NotificationPreferences:
    telegram_enabled: bool = False
    telegram_chat_id: str = ""
    alert_on_critical: bool = True
    alert_on_approval_needed: bool = True
    alert_on_budget_threshold: bool = True
    budget_alert_threshold_pct: float = 0.80
    daily_digest_enabled: bool = False
    daily_digest_hour: int = 8


@dataclass
class UserSettings:
    profile: UserProfile = field(default_factory=UserProfile)
    modes: ModePreferences = field(default_factory=ModePreferences)
    providers: ProviderPreferences = field(default_factory=ProviderPreferences)
    privacy: PrivacyPreferences = field(default_factory=PrivacyPreferences)
    interface: InterfacePreferences = field(default_factory=InterfacePreferences)
    notifications: NotificationPreferences = field(default_factory=NotificationPreferences)


class UserSettingsStore:
    """Load, validate, and persist user settings."""

    def __init__(self, path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(path)
        self._settings = self._load()

    # ------------------------------------------------------------------

    def get_all(self) -> dict[str, Any]:
        return asdict(self._settings)

    def get_section(self, section: str) -> dict[str, Any]:
        data = asdict(self._settings)
        if section not in data:
            raise KeyError(f"Unknown settings section: {section!r}")
        return data[section]

    def update_section(self, section: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Merge updates into a settings section and persist."""
        data = asdict(self._settings)
        if section not in data:
            raise KeyError(f"Unknown settings section: {section!r}")
        data[section].update(updates)
        self._settings = self._from_dict(data)
        self._validate()
        self._persist()
        return data[section]

    def update_all(self, data: dict[str, Any]) -> dict[str, Any]:
        """Replace all settings and persist."""
        merged = {**asdict(self._settings), **data}
        self._settings = self._from_dict(merged)
        self._validate()
        self._persist()
        return asdict(self._settings)

    def reset(self) -> dict[str, Any]:
        """Reset to defaults."""
        self._settings = UserSettings()
        self._persist()
        return asdict(self._settings)

    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Clamp/coerce any out-of-range values."""
        s = self._settings
        if s.modes.default_mode not in _VALID_MODES:
            s.modes.default_mode = "command"
        if s.providers.preferred_provider not in _VALID_PROVIDERS:
            s.providers.preferred_provider = "anthropic"
        if s.interface.theme not in _VALID_THEMES:
            s.interface.theme = "dark"
        if s.interface.font_size not in _VALID_FONT_SIZES:
            s.interface.font_size = "medium"
        if s.profile.language not in _VALID_LANGUAGES:
            s.profile.language = "en"
        s.providers.budget_daily_usd = max(0.0, s.providers.budget_daily_usd)
        s.providers.max_cost_per_request_usd = max(0.0, s.providers.max_cost_per_request_usd)
        s.privacy.memory_retention_days = max(1, min(3650, s.privacy.memory_retention_days))
        s.notifications.budget_alert_threshold_pct = max(0.1, min(1.0, s.notifications.budget_alert_threshold_pct))
        s.notifications.daily_digest_hour = max(0, min(23, s.notifications.daily_digest_hour))

    def _load(self) -> UserSettings:
        if not self._path.exists():
            return UserSettings()
        try:
            raw = json.loads(self._path.read_text("utf-8"))
            return self._from_dict(raw)
        except Exception as exc:
            logger.warning("UserSettingsStore load error: %s", exc)
            return UserSettings()

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(asdict(self._settings), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("UserSettingsStore persist failed: %s", exc)

    @staticmethod
    def _from_dict(d: dict) -> UserSettings:
        def _dc(cls, data):
            import dataclasses
            known = {f.name for f in dataclasses.fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in known})

        s = UserSettings()
        if "profile" in d:
            s.profile = _dc(UserProfile, d["profile"])
        if "modes" in d:
            s.modes = _dc(ModePreferences, d["modes"])
        if "providers" in d:
            s.providers = _dc(ProviderPreferences, d["providers"])
        if "privacy" in d:
            s.privacy = _dc(PrivacyPreferences, d["privacy"])
        if "interface" in d:
            s.interface = _dc(InterfacePreferences, d["interface"])
        if "notifications" in d:
            s.notifications = _dc(NotificationPreferences, d["notifications"])
        return s


# Global singleton
_store: UserSettingsStore | None = None


def get_settings_store(path: str | pathlib.Path = _DEFAULT_PATH) -> UserSettingsStore:
    global _store
    if _store is None:
        _store = UserSettingsStore(path)
    return _store
