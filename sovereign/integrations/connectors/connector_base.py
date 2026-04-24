"""
Base connector contract for all SOVEREIGN integrations.

Every connector must extend ConnectorBase and implement:
  connect(), disconnect(), sync(), health()
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ConnectorStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"
    DISABLED = "disabled"
    BETA = "beta"
    STUB = "stub"


@dataclass
class ConnectorHealth:
    connector_id: str
    status: ConnectorStatus
    last_sync: str | None = None
    last_error: str | None = None
    records_synced: int = 0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    connector_id: str
    success: bool
    records_synced: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    synced_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConnectorBase(ABC):
    """Abstract base class for all SOVEREIGN connectors."""

    connector_id: str = ""
    connector_name: str = ""
    connector_description: str = ""
    connector_status: ConnectorStatus = ConnectorStatus.STUB
    requires_oauth: bool = False
    required_scopes: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._logger = logging.getLogger(f"connector.{self.connector_id}")
        self._last_sync: str | None = None
        self._last_error: str | None = None
        self._records_synced: int = 0

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection / validate credentials. Returns True on success."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection resources."""

    @abstractmethod
    async def sync(self) -> SyncResult:
        """Pull latest data from the external service. Returns SyncResult."""

    @abstractmethod
    async def health(self) -> ConnectorHealth:
        """Return current health status of the connector."""

    def describe(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "name": self.connector_name,
            "description": self.connector_description,
            "status": self.connector_status.value,
            "requires_oauth": self.requires_oauth,
            "last_sync": self._last_sync,
            "last_error": self._last_error,
            "records_synced": self._records_synced,
        }

    def _mark_sync(self, result: SyncResult) -> None:
        self._last_sync = result.synced_at
        self._records_synced = result.records_synced
        if not result.success and result.errors:
            self._last_error = result.errors[-1]
