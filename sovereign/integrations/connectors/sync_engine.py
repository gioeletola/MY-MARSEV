"""
Sync engine — orchestrates connector sync cycles with retry, backoff, and logging.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TYPE_CHECKING

from sovereign.integrations.connectors.connector_base import ConnectorBase, SyncResult
from sovereign.integrations.connectors.connector_store import ConnectorStore, get_connector_store

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_DEFAULT_RETRY = 3
_BACKOFF_BASE = 2.0  # seconds


class SyncEngine:
    """
    Central sync orchestrator.

    Usage::
        engine = SyncEngine()
        engine.register(my_gmail_connector)
        await engine.sync_all()
        await engine.sync_one("gmail")
    """

    def __init__(self, store: ConnectorStore | None = None) -> None:
        self._connectors: dict[str, ConnectorBase] = {}
        self._store = store or get_connector_store()

    def register(self, connector: ConnectorBase) -> None:
        self._connectors[connector.connector_id] = connector
        logger.info("SyncEngine: registered %s", connector.connector_id)

    def unregister(self, connector_id: str) -> None:
        self._connectors.pop(connector_id, None)

    def list_connectors(self) -> list[dict[str, Any]]:
        return [c.describe() for c in self._connectors.values()]

    async def sync_one(self, connector_id: str, retries: int = _DEFAULT_RETRY) -> SyncResult:
        connector = self._connectors.get(connector_id)
        if connector is None:
            return SyncResult(connector_id=connector_id, success=False, errors=["Connector not registered"])

        if not self._store.is_enabled(connector_id):
            return SyncResult(connector_id=connector_id, success=False, errors=["Connector disabled"])

        last_error = ""
        for attempt in range(retries):
            try:
                t0 = time.monotonic()
                result = await connector.sync()
                result.duration_ms = (time.monotonic() - t0) * 1000
                self._store.record_sync(
                    connector_id, result.success, result.records_synced,
                    result.errors[-1] if result.errors else None,
                )
                connector._mark_sync(result)
                if result.success:
                    logger.info(
                        "SyncEngine: synced %s — %d records in %.0fms",
                        connector_id, result.records_synced, result.duration_ms,
                    )
                    return result
                last_error = result.errors[-1] if result.errors else "unknown error"
            except Exception as exc:
                last_error = str(exc)
                logger.warning("SyncEngine: %s attempt %d/%d failed: %s", connector_id, attempt+1, retries, exc)

            if attempt < retries - 1:
                backoff = _BACKOFF_BASE ** attempt
                await asyncio.sleep(backoff)

        self._store.record_sync(connector_id, False, 0, last_error)
        return SyncResult(connector_id=connector_id, success=False, errors=[last_error])

    async def sync_all(self, parallel: bool = True) -> dict[str, SyncResult]:
        enabled = [
            cid for cid in self._connectors
            if self._store.is_enabled(cid)
        ]
        if parallel:
            tasks = [self.sync_one(cid) for cid in enabled]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            output: dict[str, SyncResult] = {}
            for cid, res in zip(enabled, results):
                if isinstance(res, Exception):
                    output[cid] = SyncResult(connector_id=cid, success=False, errors=[str(res)])
                else:
                    output[cid] = res  # type: ignore[assignment]
            return output
        else:
            return {cid: await self.sync_one(cid) for cid in enabled}

    def health_summary(self) -> dict[str, Any]:
        states = self._store.all_states()
        total = len(self._connectors)
        healthy = sum(
            1 for cid in self._connectors
            if states.get(cid, {}).get("last_sync_success", False)
        )
        return {
            "total": total,
            "healthy": healthy,
            "disabled": total - len([c for c in self._connectors if self._store.is_enabled(c)]),
            "connectors": self.list_connectors(),
        }


_engine: SyncEngine | None = None


def get_sync_engine() -> SyncEngine:
    global _engine
    if _engine is None:
        _engine = SyncEngine()
    return _engine
