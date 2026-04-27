# Adding Connectors — SOVEREIGN AI OS v0.3.0

Connectors integrate external services into SOVEREIGN's memory and agent context. Every connector implements the `ConnectorBase` abstract base class defined in `sovereign/integrations/connectors/connector_base.py`.

---

## ConnectorBase ABC

```python
# sovereign/integrations/connectors/connector_base.py (reference)

class ConnectorStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"
    DISABLED = "disabled"
    BETA = "beta"
    STUB = "stub"

@dataclass
class SyncResult:
    connector_id: str
    success: bool
    records_synced: int = 0
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    synced_at: str = ...     # ISO 8601 UTC

@dataclass
class ConnectorHealth:
    connector_id: str
    status: ConnectorStatus
    last_sync: str | None = None
    last_error: str | None = None
    records_synced: int = 0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

class ConnectorBase(ABC):
    connector_id: str = ""
    connector_name: str = ""
    connector_description: str = ""
    connector_status: ConnectorStatus = ConnectorStatus.STUB
    requires_oauth: bool = False
    required_scopes: list[str] = []

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def sync(self) -> SyncResult: ...

    @abstractmethod
    async def health(self) -> ConnectorHealth: ...
```

---

## Step 1: Create the connector file

```python
# sovereign/integrations/connectors/my_connector.py
from __future__ import annotations

import os
from sovereign.integrations.connectors.connector_base import (
    ConnectorBase,
    ConnectorHealth,
    ConnectorStatus,
    SyncResult,
)


class MyConnector(ConnectorBase):
    connector_id = "my_service"
    connector_name = "My Service"
    connector_description = "Syncs data from My Service into SOVEREIGN memory."
    connector_status = ConnectorStatus.STUB   # change to BETA or CONNECTED when ready
    requires_oauth = False

    async def connect(self) -> bool:
        """Validate credentials. Return True on success, False if unavailable."""
        api_key = os.getenv("MY_SERVICE_API_KEY", "")
        if not api_key:
            self._logger.warning("MY_SERVICE_API_KEY not set")
            self.connector_status = ConnectorStatus.DISCONNECTED
            return False
        self._api_key = api_key
        self.connector_status = ConnectorStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        """Fetch latest data and write to memory. Return a SyncResult."""
        import time
        t0 = time.monotonic()
        try:
            # 1. Fetch data from the external service
            data = await self._fetch_data()

            # 2. Write relevant records to memory (optional but recommended)
            # e.g. self._memory_manager.write("project", "my_service_data", data)

            duration_ms = (time.monotonic() - t0) * 1000
            result = SyncResult(
                connector_id=self.connector_id,
                success=True,
                records_synced=len(data),
                duration_ms=duration_ms,
            )
            self._mark_sync(result)
            return result

        except Exception as exc:
            self._logger.exception("Sync failed: %s", exc)
            return SyncResult(
                connector_id=self.connector_id,
                success=False,
                errors=[str(exc)],
                duration_ms=(time.monotonic() - t0) * 1000,
            )

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=self._records_synced,
        )

    async def _fetch_data(self) -> list[dict]:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.myservice.com/v1/data",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            resp.raise_for_status()
            return resp.json().get("items", [])
```

---

## Step 2: Register in `__init__.py`

Add the import and class name to `sovereign/integrations/connectors/__init__.py`:

```python
from sovereign.integrations.connectors.my_connector import MyConnector

__all__ = [
    # ... existing connectors ...
    "MyConnector",
]
```

---

## Step 3: Add environment variables

Document the required env vars in `.env.example`:

```env
# My Service
MY_SERVICE_API_KEY=
```

---

## Step 4: Set the correct status

| Status | When to use |
|---|---|
| `STUB` | Skeleton created but `sync()` not yet implemented |
| `BETA` | Implemented and testable but API/auth flow may change |
| `CONNECTED` | Stable, production-ready |
| `DISCONNECTED` | Credentials missing or connection failed |
| `ERROR` | Sync failed with an unrecoverable error |
| `DISABLED` | Intentionally disabled by the user |

---

## OAuth Connectors

For OAuth-based connectors, set `requires_oauth = True` and list the required scopes:

```python
class MyOAuthConnector(ConnectorBase):
    connector_id = "my_oauth_service"
    requires_oauth = True
    required_scopes = ["read:data", "write:data"]

    async def connect(self) -> bool:
        # Check for stored OAuth token; trigger refresh if expired
        token = os.getenv("MY_SERVICE_ACCESS_TOKEN", "")
        ...
```

The `oauth_manager.py` helper in `sovereign/integrations/connectors/` provides token refresh logic for common OAuth flows.

---

## CLI Verification

After registration:

```bash
# Confirm the connector appears
python main.py connector list | grep my_service

# Test the connection
python main.py connector sync my_service

# Check health
python main.py connector health
```

---

## Testing Your Connector

```python
# tests/test_my_connector.py
import pytest
from unittest.mock import AsyncMock, patch
from sovereign.integrations.connectors.my_connector import MyConnector

@pytest.mark.asyncio
async def test_connect_without_key():
    conn = MyConnector()
    result = await conn.connect()
    assert result is False

@pytest.mark.asyncio
async def test_sync_success():
    conn = MyConnector()
    conn._api_key = "test_key"
    conn.connector_status = conn.connector_status.CONNECTED

    mock_data = [{"id": 1}, {"id": 2}]
    with patch.object(conn, "_fetch_data", AsyncMock(return_value=mock_data)):
        result = await conn.sync()

    assert result.success is True
    assert result.records_synced == 2
```
