"""Tests for memory manager and all 14 memory domains."""
from __future__ import annotations
import tempfile
import pytest
import pytest_asyncio

from sovereign.memory.memory_manager import MemoryManager

_ALL_14_DOMAINS = [
    "identity", "operational", "project", "relationship", "financial",
    "learning", "inventory", "health_routine", "diary", "legal_compliance",
    "decision", "research", "content", "brand",
]


@pytest.mark.asyncio
async def test_write_and_read_domain(tmp_path):
    mem = MemoryManager(data_dir=str(tmp_path))
    await mem.write("identity", "profile", {"name": "Test User", "version": 1})
    result = await mem.read("identity", "profile")
    assert result is not None
    assert result.get("name") == "Test User"


@pytest.mark.asyncio
async def test_read_nonexistent_key_returns_none(tmp_path):
    """Reading a valid domain but missing key returns None."""
    mem = MemoryManager(data_dir=str(tmp_path))
    result = await mem.read("identity", "key_that_does_not_exist_xyz")
    assert result is None or result == {}


@pytest.mark.asyncio
async def test_overwrite_domain(tmp_path):
    mem = MemoryManager(data_dir=str(tmp_path))
    await mem.write("operational", "status", {"status": "first"})
    await mem.write("operational", "status", {"status": "second"})
    result = await mem.read("operational", "status")
    assert result["status"] == "second"


@pytest.mark.asyncio
@pytest.mark.parametrize("domain", _ALL_14_DOMAINS)
async def test_write_read_all_14_domains(tmp_path, domain):
    mem = MemoryManager(data_dir=str(tmp_path))
    payload = {"domain": domain, "test": True, "value": 42}
    await mem.write(domain, "test_key", payload)
    result = await mem.read(domain, "test_key")
    assert result is not None
    assert result.get("domain") == domain


@pytest.mark.asyncio
async def test_get_snapshot_returns_dict(tmp_path):
    mem = MemoryManager(data_dir=str(tmp_path))
    await mem.write("identity", "snap_key", {"x": 1})
    snapshot = await mem.get_snapshot()
    assert isinstance(snapshot, dict)


@pytest.mark.asyncio
async def test_memory_manager_supports_all_14_domains(tmp_path):
    """MemoryManager should support all 14 canonical domains without error."""
    mem = MemoryManager(data_dir=str(tmp_path))
    for domain in _ALL_14_DOMAINS:
        await mem.write(domain, "probe", {"ok": True})
        result = await mem.read(domain, "probe")
        assert result is not None, f"Domain {domain} failed read"
