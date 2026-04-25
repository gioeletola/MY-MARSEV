"""
ConversationStore — multi-turn conversation persistence for SOVEREIGN AI OS.

Persists session turns to JSONL per session_id so that handle_request()
can inject recent conversation history into the dynamic prompt section.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_CONV_DIR = pathlib.Path("data/conversations")


@dataclass
class ConversationTurn:
    role: str                    # "user" | "assistant"
    content: str
    session_id: str
    turn_index: int
    timestamp: str = ""
    mode: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConversationStore:
    """
    Append-only conversation store backed by per-session JSONL files.

    Data layout:
      data/conversations/<conversation_id>.jsonl
        — one JSON object per line, each a ConversationTurn

    A `conversation_id` is typically a stable user/device identifier
    (e.g. "default" or the user_id) so history persists across sessions.
    Internally it keeps an in-memory ring buffer (last `max_turns` turns)
    per conversation_id to avoid re-reading large JSONL files on every call.
    """

    def __init__(
        self,
        data_dir: pathlib.Path = _CONV_DIR,
        max_turns: int = 20,
    ) -> None:
        self._dir = data_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_turns = max_turns
        # conversation_id → list of turns (ring buffer)
        self._cache: dict[str, list[ConversationTurn]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(
        self,
        conversation_id: str,
        role: str,
        content: str,
        session_id: str = "",
        mode: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ConversationTurn:
        """Append a turn to a conversation."""
        turns = self._get_or_load(conversation_id)
        turn = ConversationTurn(
            role=role,
            content=content,
            session_id=session_id,
            turn_index=len(turns),
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=mode,
            metadata=metadata or {},
        )
        turns.append(turn)
        if len(turns) > self._max_turns:
            turns = turns[-self._max_turns :]
        self._cache[conversation_id] = turns
        self._persist_turn(conversation_id, turn)
        return turn

    def recent(self, conversation_id: str, n: int = 10) -> list[ConversationTurn]:
        """Return the last `n` turns for a conversation."""
        turns = self._get_or_load(conversation_id)
        return turns[-n:]

    def to_messages(
        self,
        conversation_id: str,
        n: int = 10,
    ) -> list[dict[str, str]]:
        """Return turns formatted as Anthropic messages API objects."""
        turns = self.recent(conversation_id, n)
        return [{"role": t.role, "content": t.content} for t in turns]

    def to_context_string(self, conversation_id: str, n: int = 6) -> str:
        """Compact text summary of recent turns for prompt injection."""
        turns = self.recent(conversation_id, n)
        if not turns:
            return ""
        lines = []
        for t in turns:
            prefix = "You" if t.role == "user" else "SOVEREIGN"
            snippet = t.content[:200].replace("\n", " ")
            lines.append(f"{prefix}: {snippet}")
        return "\n".join(lines)

    def clear(self, conversation_id: str) -> None:
        """Delete all turns for a conversation (in-memory + file)."""
        self._cache.pop(conversation_id, None)
        path = self._path(conversation_id)
        if path.exists():
            path.unlink()

    def list_conversations(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.jsonl")]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _path(self, conversation_id: str) -> pathlib.Path:
        safe = "".join(c for c in conversation_id if c.isalnum() or c in "-_")
        return self._dir / f"{safe}.jsonl"

    def _persist_turn(self, conversation_id: str, turn: ConversationTurn) -> None:
        with open(self._path(conversation_id), "a") as f:
            f.write(json.dumps(turn.to_dict(), default=str) + "\n")

    def _get_or_load(self, conversation_id: str) -> list[ConversationTurn]:
        if conversation_id in self._cache:
            return self._cache[conversation_id]
        turns = self._load_from_disk(conversation_id)
        self._cache[conversation_id] = turns
        return turns

    def _load_from_disk(self, conversation_id: str) -> list[ConversationTurn]:
        path = self._path(conversation_id)
        if not path.exists():
            return []
        turns: list[ConversationTurn] = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    turns.append(ConversationTurn(**{
                        k: v for k, v in d.items()
                        if k in ConversationTurn.__dataclass_fields__
                    }))
                except Exception:
                    pass
        # Keep only the last max_turns
        return turns[-self._max_turns :]


# Module-level singleton
_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
