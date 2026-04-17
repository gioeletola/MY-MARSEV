"""Integration Manager — lifecycle controller for all external connectors."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from sovereign.integrations.analytics_integration import AnalyticsIntegration
from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)
from sovereign.integrations.calendar_integration import CalendarIntegration
from sovereign.integrations.crm_integration import CRMIntegration
from sovereign.integrations.email_integration import EmailIntegration
from sovereign.integrations.telegram_integration import TelegramIntegration

logger = logging.getLogger(__name__)

# Path where integration configs are persisted on disk.
_CONFIG_PATH = Path("data/memory/integrations.json")


class IntegrationManager:
    """Manages all integration connectors for the SOVEREIGN AI OS.

    On instantiation every connector is registered; individual integrations are
    activated by calling :meth:`connect` with an appropriate
    :class:`~sovereign.integrations.base_integration.IntegrationConfig`.

    Config state is persisted to ``data/memory/integrations.json`` so that
    connection metadata survives process restarts.
    """

    def __init__(self) -> None:
        self._integrations: dict[str, BaseIntegration] = {}
        self._configs: dict[str, dict] = {}

        # Register all built-in connectors.
        for connector in (
            EmailIntegration(),
            CalendarIntegration(),
            TelegramIntegration(),
            CRMIntegration(),
            AnalyticsIntegration(),
        ):
            self._integrations[connector.integration_id] = connector
            logger.debug(
                "integration_manager.__init__: registered %s",
                connector.integration_id,
            )

        self._load_configs()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, integration_id: str) -> BaseIntegration | None:
        """Return the connector for *integration_id*, or ``None`` if unknown."""
        return self._integrations.get(integration_id)

    def list_all(self) -> list[dict]:
        """Return a lightweight summary of every registered integration.

        Each entry is ``{id, name, status}``.
        """
        return [
            {
                "id": connector.integration_id,
                "name": connector.name,
                "status": connector.status.value,
            }
            for connector in self._integrations.values()
        ]

    def connect(self, integration_id: str, config: IntegrationConfig) -> bool:
        """Attempt to connect *integration_id* using *config*.

        Persists the config on success.
        """
        connector = self._integrations.get(integration_id)
        if connector is None:
            logger.warning(
                "integration_manager.connect: unknown integration %r",
                integration_id,
            )
            return False

        if not config.enabled:
            logger.debug(
                "integration_manager.connect: %s is disabled — skipping",
                integration_id,
            )
            return False

        result = connector.connect(config)
        if result:
            self._configs[integration_id] = self._config_to_dict(config)
            self._persist_configs()
            logger.debug(
                "integration_manager.connect: %s connected successfully",
                integration_id,
            )
        else:
            logger.debug(
                "integration_manager.connect: %s connect returned False",
                integration_id,
            )
        return result

    def disconnect(self, integration_id: str) -> bool:
        """Disconnect *integration_id*.

        Removes persisted config on success.
        """
        connector = self._integrations.get(integration_id)
        if connector is None:
            logger.warning(
                "integration_manager.disconnect: unknown integration %r",
                integration_id,
            )
            return False

        result = connector.disconnect()
        if result:
            self._configs.pop(integration_id, None)
            self._persist_configs()
            logger.debug(
                "integration_manager.disconnect: %s disconnected",
                integration_id,
            )
        return result

    def health(self) -> dict:
        """Return ``{integration_id: status_value}`` for every connector."""
        return {
            iid: connector.status.value
            for iid, connector in self._integrations.items()
        }

    def enabled_integrations(self) -> list[str]:
        """Return the IDs of every connector that is not DISABLED."""
        return [
            iid
            for iid, connector in self._integrations.items()
            if connector.status != IntegrationStatus.DISABLED
        ]

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _config_to_dict(config: IntegrationConfig) -> dict:
        return {
            "integration_id": config.integration_id,
            "name": config.name,
            "enabled": config.enabled,
            "credentials": config.credentials,
            "settings": config.settings,
            "created_at": config.created_at,
            "last_connected": config.last_connected,
        }

    def _persist_configs(self) -> None:
        """Write current configs to ``data/memory/integrations.json``."""
        try:
            _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            _CONFIG_PATH.write_text(
                json.dumps(self._configs, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("integration_manager: configs persisted to %s", _CONFIG_PATH)
        except OSError as exc:
            logger.error(
                "integration_manager: failed to persist configs — %s", exc
            )

    def _load_configs(self) -> None:
        """Load previously persisted configs from disk, if the file exists."""
        if not _CONFIG_PATH.exists():
            logger.debug(
                "integration_manager: no persisted config found at %s", _CONFIG_PATH
            )
            return

        try:
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._configs = raw
                logger.debug(
                    "integration_manager: loaded %d config(s) from %s",
                    len(self._configs),
                    _CONFIG_PATH,
                )
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "integration_manager: could not load configs — %s", exc
            )
