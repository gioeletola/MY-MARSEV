"""
Connector store — persists connector state and sync history.
"""
from __future__ import annotations

import json
import logging
import pathlib
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_STORE_PATH = pathlib.Path("data/connectors/state.json")


class ConnectorStore:
    """Persists connector state: config, last sync, sync history, enable/disable."""

    def __init__(self, store_path: pathlib.Path | None = None) -> None:
        self._path = store_path or _STORE_PATH
        self._state: dict[str, dict[str, Any]] = {}
        self._load()

    def save_state(self, connector_id: str, state: dict[str, Any]) -> None:
        self._state[connector_id] = {
            **self._state.get(connector_id, {}),
            **state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._persist()

    def get_state(self, connector_id: str) -> dict[str, Any]:
        return self._state.get(connector_id, {})

    def all_states(self) -> dict[str, dict[str, Any]]:
        return dict(self._state)

    def record_sync(self, connector_id: str, success: bool, records: int, error: str | None = None) -> None:
        entry = self._state.setdefault(connector_id, {})
        entry["last_sync"] = datetime.now(timezone.utc).isoformat()
        entry["last_sync_success"] = success
        entry["last_sync_records"] = records
        if error:
            entry["last_error"] = error
        history = entry.setdefault("sync_history", [])
        history.append({
            "at": entry["last_sync"],
            "success": success,
            "records": records,
        })
        # Keep only last 20 sync records
        entry["sync_history"] = history[-20:]
        self._persist()

    def enable(self, connector_id: str) -> None:
        self.save_state(connector_id, {"enabled": True})

    def disable(self, connector_id: str) -> None:
        self.save_state(connector_id, {"enabled": False})

    def is_enabled(self, connector_id: str) -> bool:
        return self._state.get(connector_id, {}).get("enabled", True)

    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            self._state = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("ConnectorStore: failed to load: %s", exc)

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("ConnectorStore: failed to persist: %s", exc)


_store: ConnectorStore | None = None


def get_connector_store() -> ConnectorStore:
    global _store
    if _store is None:
        _store = ConnectorStore()
    return _store
