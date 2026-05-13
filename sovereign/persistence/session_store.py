"""SQLite-backed chat session store."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

_DEFAULT_DB = Path("data/sessions.db")


class SessionStore:
    def __init__(self, db_path: str | Path = _DEFAULT_DB) -> None:
        self._db = Path(db_path)
        self._db.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    mode TEXT DEFAULT 'command',
                    metadata TEXT DEFAULT '{}'
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts REAL NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )""")
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, ts)"
            )

    def create_session(
        self, session_id: str | None = None, mode: str = "command"
    ) -> str:
        sid = session_id or str(uuid.uuid4())[:12]
        now = time.time()
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO sessions VALUES (?,?,?,?,?)",
                (sid, now, now, mode, "{}"),
            )
        return sid

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        self.create_session(session_id)
        with self._conn() as c:
            c.execute(
                "INSERT INTO messages (session_id,role,content,ts,metadata) VALUES (?,?,?,?,?)",
                (session_id, role, content, time.time(), json.dumps(metadata or {})),
            )
            c.execute(
                "UPDATE sessions SET updated_at=? WHERE session_id=?",
                (time.time(), session_id),
            )

    def get_history(
        self, session_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT role,content,ts FROM messages"
                " WHERE session_id=? ORDER BY ts DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "ts": r["ts"]}
            for r in reversed(rows)
        ]

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT session_id,created_at,updated_at,mode FROM sessions"
                " ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            c.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
