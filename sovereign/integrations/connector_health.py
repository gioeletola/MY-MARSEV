"""ConnectorHealthMonitor — periodic health checks for all registered connectors."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConnectorHealthReport:
    connector_id: str
    status: str               # healthy / degraded / down / unknown
    latency_ms: float = 0.0
    last_sync: str = ""
    errors: list[str] = field(default_factory=list)
    uptime_pct: float = 100.0
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"


class ConnectorHealthMonitor:
    """
    Periodically checks all registered connectors and reports their health.

    Usage::
        monitor = ConnectorHealthMonitor(registry)
        reports = await monitor.check_all()
        degraded = monitor.get_degraded()
    """

    def __init__(self, registry: Any = None) -> None:
        self._registry = registry
        self._reports: dict[str, ConnectorHealthReport] = {}
        self._check_counts: dict[str, int] = {}
        self._fail_counts: dict[str, int] = {}
        self._background_task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def check_all(self) -> list[ConnectorHealthReport]:
        """Run health checks for every registered connector."""
        reports: list[ConnectorHealthReport] = []
        connectors = self._get_connectors()
        if not connectors:
            return reports

        results = await asyncio.gather(
            *(self._check_one(c) for c in connectors),
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, ConnectorHealthReport):
                self._reports[r.connector_id] = r
                reports.append(r)
            elif isinstance(r, Exception):
                logger.warning("ConnectorHealthMonitor: check failed: %s", r)
        return reports

    async def check(self, connector_id: str) -> ConnectorHealthReport:
        """Check a single connector by ID."""
        connectors = {c.connector_id: c for c in self._get_connectors()}
        if connector_id not in connectors:
            return ConnectorHealthReport(connector_id, "unknown", errors=["Connector not found"])
        return await self._check_one(connectors[connector_id])

    def get_degraded(self) -> list[str]:
        """Return connector IDs that are degraded or down."""
        return [cid for cid, r in self._reports.items() if not r.is_healthy]

    def get_report(self, connector_id: str) -> ConnectorHealthReport | None:
        return self._reports.get(connector_id)

    def all_reports(self) -> list[ConnectorHealthReport]:
        return list(self._reports.values())

    def summary(self) -> dict[str, Any]:
        reports = list(self._reports.values())
        total = len(reports)
        healthy = sum(1 for r in reports if r.is_healthy)
        return {
            "total": total,
            "healthy": healthy,
            "degraded": total - healthy,
            "health_pct": round(healthy / total * 100, 1) if total else 100.0,
            "avg_latency_ms": round(
                sum(r.latency_ms for r in reports) / total, 1
            ) if total else 0.0,
        }

    async def start_background(self, interval_seconds: int = 300) -> None:
        """Start a background loop that checks all connectors every interval."""
        if self._background_task and not self._background_task.done():
            return

        async def _loop() -> None:
            while True:
                try:
                    await self.check_all()
                    logger.debug("ConnectorHealthMonitor: checked all connectors")
                except Exception as exc:
                    logger.warning("ConnectorHealthMonitor: background error: %s", exc)
                await asyncio.sleep(interval_seconds)

        self._background_task = asyncio.create_task(_loop())

    def stop_background(self) -> None:
        if self._background_task:
            self._background_task.cancel()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _check_one(self, connector: Any) -> ConnectorHealthReport:
        cid = getattr(connector, "connector_id", str(connector))
        self._check_counts[cid] = self._check_counts.get(cid, 0) + 1
        t0 = time.monotonic()
        errors: list[str] = []
        status = "unknown"
        last_sync = ""

        try:
            health = await asyncio.wait_for(connector.health(), timeout=10.0)
            latency = (time.monotonic() - t0) * 1000
            if hasattr(health, "status"):
                status = health.status.value if hasattr(health.status, "value") else str(health.status)
            elif isinstance(health, dict):
                status = health.get("status", "healthy")
            else:
                status = "healthy"
            last_sync = getattr(health, "last_sync", "") or ""
            if hasattr(health, "errors") and health.errors:
                errors = list(health.errors)
        except TimeoutError:
            latency = (time.monotonic() - t0) * 1000
            status = "down"
            errors = ["Health check timed out after 10s"]
            self._fail_counts[cid] = self._fail_counts.get(cid, 0) + 1
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            status = "degraded"
            errors = [str(exc)]
            self._fail_counts[cid] = self._fail_counts.get(cid, 0) + 1

        checks = self._check_counts.get(cid, 1)
        fails = self._fail_counts.get(cid, 0)
        uptime = round((1 - fails / checks) * 100, 1) if checks else 100.0

        return ConnectorHealthReport(
            connector_id=cid,
            status=status,
            latency_ms=round(latency, 2),
            last_sync=last_sync,
            errors=errors,
            uptime_pct=uptime,
        )

    def _get_connectors(self) -> list[Any]:
        if self._registry is None:
            return []
        if hasattr(self._registry, "all"):
            return self._registry.all()
        if hasattr(self._registry, "list_connectors"):
            return self._registry.list_connectors()
        return []
