"""
Integration Registry — catalog of external service integrations.

Tracks MCP servers, webhooks, API credentials (by name only — never stores secrets),
and integration health status.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IntegrationRecord:
    """Descriptor for one external integration."""
    integration_id: str
    name: str
    kind: str              # "mcp_server" | "webhook" | "oauth" | "api_key" | "database"
    description: str
    enabled: bool = True
    health: str = "unknown"   # "healthy" | "degraded" | "down" | "unknown"
    last_check: str = ""
    config: dict[str, Any] = field(default_factory=dict)  # non-secret config only
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class IntegrationRegistry:
    """
    Central catalog of all external integrations.

    Usage:
        registry = IntegrationRegistry()
        registry.register(IntegrationRecord(
            integration_id="gmail",
            name="Gmail MCP",
            kind="mcp_server",
            description="Email integration via MCP",
        ))
        registry.set_health("gmail", "healthy")
    """

    def __init__(self) -> None:
        self._integrations: dict[str, IntegrationRecord] = {}

    def register(self, record: IntegrationRecord) -> None:
        """Register or update an integration."""
        self._integrations[record.integration_id] = record
        logger.info("IntegrationRegistry: registered %s (%s)", record.name, record.kind)

    def unregister(self, integration_id: str) -> bool:
        if integration_id in self._integrations:
            del self._integrations[integration_id]
            return True
        return False

    def get(self, integration_id: str) -> IntegrationRecord | None:
        return self._integrations.get(integration_id)

    def list_all(self) -> list[IntegrationRecord]:
        return list(self._integrations.values())

    def list_by_kind(self, kind: str) -> list[IntegrationRecord]:
        return [r for r in self._integrations.values() if r.kind == kind]

    def list_enabled(self) -> list[IntegrationRecord]:
        return [r for r in self._integrations.values() if r.enabled]

    def set_health(self, integration_id: str, health: str) -> None:
        record = self._integrations.get(integration_id)
        if record:
            record.health = health
            record.last_check = datetime.now(timezone.utc).isoformat()
            logger.debug("Integration %s health → %s", integration_id, health)

    def enable(self, integration_id: str) -> None:
        record = self._integrations.get(integration_id)
        if record:
            record.enabled = True

    def disable(self, integration_id: str) -> None:
        record = self._integrations.get(integration_id)
        if record:
            record.enabled = False

    def unhealthy(self) -> list[IntegrationRecord]:
        return [
            r for r in self._integrations.values()
            if r.health in ("degraded", "down") and r.enabled
        ]

    def dashboard(self) -> dict[str, Any]:
        all_recs = list(self._integrations.values())
        return {
            "total": len(all_recs),
            "enabled": sum(1 for r in all_recs if r.enabled),
            "healthy": sum(1 for r in all_recs if r.health == "healthy"),
            "unhealthy": [r.integration_id for r in self.unhealthy()],
            "by_kind": {
                kind: sum(1 for r in all_recs if r.kind == kind)
                for kind in {r.kind for r in all_recs}
            },
        }
