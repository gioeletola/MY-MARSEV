"""Base integration protocol for all external service connectors."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class IntegrationStatus(str, Enum):
    """Lifecycle state of an integration connector."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class IntegrationConfig:
    """Holds runtime configuration for a single integration."""

    integration_id: str
    name: str
    enabled: bool
    credentials: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    created_at: str = ""
    last_connected: str = ""


class BaseIntegration(ABC):
    """Abstract base class that every integration connector must implement."""

    integration_id: str = ""
    name: str = ""

    def __init__(self) -> None:
        self._status: IntegrationStatus = IntegrationStatus.DISCONNECTED
        self._last_error: str = ""

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def connect(self, config: IntegrationConfig) -> bool:
        """Establish a connection to the external service.

        Returns True on success, False otherwise.
        """

    @abstractmethod
    def disconnect(self) -> bool:
        """Tear down the current connection.

        Returns True on success, False otherwise.
        """

    @abstractmethod
    def test_connection(self) -> bool:
        """Probe the connection and return True if it is healthy."""

    @abstractmethod
    def fetch(self, resource: str, params: dict) -> dict:
        """Read *resource* from the external service with *params* filters."""

    @abstractmethod
    def push(self, resource: str, data: dict) -> dict:
        """Write *data* to *resource* on the external service."""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> IntegrationStatus:
        """Current connection status."""
        return self._status

    @property
    def last_error(self) -> str:
        """Human-readable description of the most recent error, if any."""
        return self._last_error
