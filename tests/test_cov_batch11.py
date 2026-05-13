"""Coverage batch 11 — session store, backup manager, API rate limiter, code_exec sandbox."""
from __future__ import annotations

import asyncio
import time

import pytest


# ---------------------------------------------------------------------------
# SessionStore
# ---------------------------------------------------------------------------

class TestSessionStore:
    def test_create_and_list(self, tmp_path):
        from sovereign.persistence.session_store import SessionStore
        store = SessionStore(db_path=tmp_path / "s.db")
        sid = store.create_session(mode="research")
        sessions = store.list_sessions()
        assert any(s["session_id"] == sid for s in sessions)

    def test_add_and_get_messages(self, tmp_path):
        from sovereign.persistence.session_store import SessionStore
        store = SessionStore(db_path=tmp_path / "s.db")
        sid = store.create_session()
        store.add_message(sid, "user", "hello")
        store.add_message(sid, "assistant", "hi there")
        history = store.get_history(sid)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert "hello" in history[0]["content"]

    def test_history_limit(self, tmp_path):
        from sovereign.persistence.session_store import SessionStore
        store = SessionStore(db_path=tmp_path / "s.db")
        sid = store.create_session()
        for i in range(10):
            store.add_message(sid, "user", f"msg {i}")
        history = store.get_history(sid, limit=3)
        assert len(history) == 3

    def test_delete_session(self, tmp_path):
        from sovereign.persistence.session_store import SessionStore
        store = SessionStore(db_path=tmp_path / "s.db")
        sid = store.create_session()
        store.add_message(sid, "user", "test")
        store.delete_session(sid)
        assert store.get_history(sid) == []

    def test_auto_create_on_add_message(self, tmp_path):
        from sovereign.persistence.session_store import SessionStore
        store = SessionStore(db_path=tmp_path / "s.db")
        store.add_message("new-session", "user", "auto-create")
        history = store.get_history("new-session")
        assert len(history) == 1

    def test_list_sessions_order(self, tmp_path):
        from sovereign.persistence.session_store import SessionStore
        store = SessionStore(db_path=tmp_path / "s.db")
        store.create_session()
        time.sleep(0.01)
        s2 = store.create_session()
        store.add_message(s2, "user", "latest")
        sessions = store.list_sessions()
        assert sessions[0]["session_id"] == s2


# ---------------------------------------------------------------------------
# BackupManager
# ---------------------------------------------------------------------------

class TestBackupManager:
    def test_backup_and_list(self, tmp_path):
        from sovereign.infra.backup_manager import BackupManager
        data = tmp_path / "data"
        mem = data / "memory"
        mem.mkdir(parents=True)
        (mem / "identity.json").write_text('{"name": "test"}')

        bm = BackupManager(data_dir=str(data), max_backups=3)
        asyncio.run(bm._do_backup())
        backups = bm.list_backups()
        assert len(backups) == 1
        assert "memory_" in backups[0]

    def test_prune_keeps_max(self, tmp_path):
        from sovereign.infra.backup_manager import BackupManager
        data = tmp_path / "data"
        bm = BackupManager(data_dir=str(data), max_backups=2)
        bm._backup_dir.mkdir(parents=True, exist_ok=True)
        # Create 4 fake backup dirs directly (no copytree needed)
        for i in range(4):
            (bm._backup_dir / f"memory_202601{i:02d}_000000").mkdir()
        asyncio.run(bm._prune())
        assert len(bm.list_backups()) <= 2

    def test_restore(self, tmp_path):
        from sovereign.infra.backup_manager import BackupManager
        data = tmp_path / "data"
        mem = data / "memory"
        mem.mkdir(parents=True)
        (mem / "id.json").write_text('{"v": 1}')

        bm = BackupManager(data_dir=str(data))
        asyncio.run(bm._do_backup())
        backup_name = bm.list_backups()[0].split("/")[-1]

        (mem / "id.json").write_text('{"v": 2}')
        bm.restore(backup_name)
        content = (mem / "id.json").read_text()
        assert '"v": 1' in content

    def test_restore_not_found(self, tmp_path):
        from sovereign.infra.backup_manager import BackupManager
        bm = BackupManager(data_dir=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            bm.restore("nonexistent_backup")

    def test_no_backup_if_memory_missing(self, tmp_path):
        from sovereign.infra.backup_manager import BackupManager
        bm = BackupManager(data_dir=str(tmp_path))
        asyncio.run(bm._do_backup())
        assert bm.list_backups() == []


# ---------------------------------------------------------------------------
# API rate limiter
# ---------------------------------------------------------------------------

class TestAPIRateLimiter:
    def test_allows_under_limit(self):
        from sovereign.api.server import _api_rate_check, _api_calls
        ip = "test-rate-ip-allow"
        _api_calls.pop(ip, None)
        for _ in range(5):
            assert _api_rate_check(ip) is True

    def test_blocks_over_limit(self):
        from sovereign.api.server import _api_rate_check, _api_calls, _API_RATE_MAX
        ip = "test-rate-ip-block"
        _api_calls.pop(ip, None)
        for _ in range(_API_RATE_MAX):
            _api_rate_check(ip)
        assert _api_rate_check(ip) is False


# ---------------------------------------------------------------------------
# code_exec unshare detection
# ---------------------------------------------------------------------------

def test_unshare_flag_is_bool():
    from sovereign.tools.builtin.code_exec import _UNSHARE_NET_AVAILABLE
    assert isinstance(_UNSHARE_NET_AVAILABLE, bool)


@pytest.mark.asyncio
async def test_code_exec_basic_still_works():
    from sovereign.tools.builtin.code_exec import CodeExecTool
    tool = CodeExecTool()
    result = await tool.execute(code="print(2 + 2)")
    assert result["exit_code"] == 0
    assert "4" in result["stdout"]
