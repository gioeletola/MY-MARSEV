import json
import logging
import os
import tempfile
import threading
from pathlib import Path

from .types import ChatMessage, ChatSession, MessageRole, SessionStatus

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self, persist_path: Path | None = None) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()
        self._path = persist_path
        if persist_path and persist_path.exists():
            self._load()

    def create(self, title: str = "New Conversation", mode: str = "chat", model: str = "") -> ChatSession:
        s = ChatSession(title=title, mode=mode, model=model)
        with self._lock:
            self._sessions[s.session_id] = s
        return s

    def get(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self, limit: int = 50) -> list[ChatSession]:
        sessions = list(self._sessions.values())
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def delete(self, session_id: str) -> bool:
        with self._lock:
            existed = session_id in self._sessions
            self._sessions.pop(session_id, None)
        return existed

    def end_session(self, session_id: str) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.status = SessionStatus.ENDED

    def save(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {}
        for sid, sess in self._sessions.items():
            payload[sid] = {
                "session_id": sess.session_id,
                "title": sess.title,
                "mode": sess.mode,
                "model": sess.model,
                "status": sess.status.value,
                "created_at": sess.created_at,
                "updated_at": sess.updated_at,
                "token_count": sess.token_count,
                "messages": [
                    {"role": m.role.value, "content": m.content, "timestamp": m.timestamp}
                    for m in sess.messages
                ],
            }
        fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp, str(self._path))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text())
            for sid, raw in data.items():
                s = ChatSession(
                    session_id=raw["session_id"],
                    title=raw.get("title", "Conversation"),
                    mode=raw.get("mode", "chat"),
                    model=raw.get("model", ""),
                    status=SessionStatus(raw.get("status", "active")),
                    created_at=raw.get("created_at", ""),
                    updated_at=raw.get("updated_at", ""),
                    token_count=raw.get("token_count", 0),
                )
                for m in raw.get("messages", []):
                    s.messages.append(
                        ChatMessage(
                            role=MessageRole(m["role"]),
                            content=m["content"],
                            timestamp=m.get("timestamp", ""),
                        )
                    )
                self._sessions[sid] = s
        except Exception as exc:
            logger.warning("SessionStore: failed to load: %s", exc)
