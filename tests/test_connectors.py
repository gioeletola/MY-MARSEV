"""Tests for sovereign/integrations/connectors/ fabric."""
from __future__ import annotations

import pytest

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)
from sovereign.integrations.connectors.connector_store import ConnectorStore
from sovereign.integrations.connectors.sync_engine import SyncEngine
from sovereign.integrations.connectors.weather_connector import WeatherConnector
from sovereign.integrations.connectors.github_connector import GitHubConnector
from sovereign.integrations.connectors.notion_connector import NotionConnector
from sovereign.integrations.connectors.gmail_connector import GmailConnector


# ---------------------------------------------------------------------------
# Stub connector
# ---------------------------------------------------------------------------

class _StubConnector(ConnectorBase):
    connector_id = "stub"
    connector_name = "Stub"
    connector_description = "Test stub connector."
    requires_oauth = False

    def __init__(self, *, fail_connect: bool = False, fail_sync: bool = False):
        super().__init__()
        self._fail_connect = fail_connect
        self._fail_sync = fail_sync

    async def connect(self) -> bool:
        if self._fail_connect:
            return False
        self.connector_status = ConnectorStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if self._fail_sync:
            return SyncResult(connector_id=self.connector_id, success=False, errors=["fail"])
        return SyncResult(connector_id=self.connector_id, success=True, records_synced=7)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
        )


# ---------------------------------------------------------------------------
# ConnectorBase
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stub_connector_connect():
    c = _StubConnector()
    ok = await c.connect()
    assert ok is True
    assert c.connector_status == ConnectorStatus.CONNECTED


@pytest.mark.asyncio
async def test_stub_connector_connect_fail():
    c = _StubConnector(fail_connect=True)
    ok = await c.connect()
    assert ok is False


@pytest.mark.asyncio
async def test_stub_connector_sync_success():
    c = _StubConnector()
    result = await c.sync()
    assert result.success is True
    assert result.records_synced == 7


@pytest.mark.asyncio
async def test_stub_connector_sync_fail():
    c = _StubConnector(fail_sync=True)
    result = await c.sync()
    assert result.success is False
    assert "fail" in result.errors


@pytest.mark.asyncio
async def test_stub_connector_health():
    c = _StubConnector()
    await c.connect()
    h = await c.health()
    assert h.status == ConnectorStatus.CONNECTED


# ---------------------------------------------------------------------------
# ConnectorStore
# ---------------------------------------------------------------------------

def test_connector_store_save_and_load():
    import pathlib
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = pathlib.Path(td) / "connectors.json"
        store = ConnectorStore(store_path=path)

        store.save_state("github", {"token": "abc", "status": "connected"})
        state = store.get_state("github")
        assert state is not None
        assert state["token"] == "abc"


def test_connector_store_missing_key():
    import pathlib
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = pathlib.Path(td) / "connectors.json"
        store = ConnectorStore(store_path=path)
        # get_state returns empty dict for unknown keys
        assert store.get_state("nonexistent") == {}


def test_connector_store_record_sync():
    import pathlib
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = pathlib.Path(td) / "connectors.json"
        store = ConnectorStore(store_path=path)
        store.record_sync("weather", success=True, records=42)
        state = store.get_state("weather")
        history = state.get("sync_history", [])
        assert len(history) == 1
        assert history[0]["records"] == 42
        assert history[0]["success"] is True


# ---------------------------------------------------------------------------
# SyncEngine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_engine_sync_one():
    engine = SyncEngine()
    stub = _StubConnector()
    engine.register(stub)
    result = await engine.sync_one("stub")
    assert result is not None
    assert result.success is True


@pytest.mark.asyncio
async def test_sync_engine_sync_all():
    engine = SyncEngine()
    engine.register(_StubConnector())
    results = await engine.sync_all()
    # sync_all returns dict[connector_id, SyncResult]
    assert len(results) == 1
    assert results["stub"].success is True


@pytest.mark.asyncio
async def test_sync_engine_unknown_connector():
    engine = SyncEngine()
    result = await engine.sync_one("unknown")
    assert result is None or result.success is False


# ---------------------------------------------------------------------------
# Connector instantiation (smoke tests — no network)
# ---------------------------------------------------------------------------

def test_weather_connector_instantiates():
    c = WeatherConnector({"location": "Rome"})
    assert c.connector_id == "weather"
    assert c.requires_oauth is False


def test_github_connector_no_token():
    import os
    old = os.environ.pop("GITHUB_TOKEN", None)
    try:
        c = GitHubConnector()
        assert c._token == ""
    finally:
        if old is not None:
            os.environ["GITHUB_TOKEN"] = old


def test_notion_connector_instantiates():
    c = NotionConnector()
    assert c.connector_id == "notion"
    assert c.requires_oauth is True


def test_gmail_connector_instantiates():
    c = GmailConnector()
    assert c.connector_id == "gmail"
    assert c.requires_oauth is True


def test_gmail_connector_custom_max_results():
    c = GmailConnector({"max_results": 50})
    assert c._max_results == 50
