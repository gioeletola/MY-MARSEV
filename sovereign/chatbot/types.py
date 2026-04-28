from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


@dataclass
class ChatMessage:
    role: MessageRole
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_api_dict(self) -> dict:
        return {"role": self.role.value, "content": self.content}


@dataclass
class ChatSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "New Conversation"
    messages: list[ChatMessage] = field(default_factory=list)
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    mode: str = "chat"
    model: str = ""
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: MessageRole, content: str, **meta) -> ChatMessage:
        msg = ChatMessage(role=role, content=content, metadata=meta)
        self.messages.append(msg)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return msg

    def to_api_messages(self) -> list[dict]:
        return [m.to_api_dict() for m in self.messages if m.role != MessageRole.SYSTEM]

    def last_n(self, n: int) -> list[ChatMessage]:
        return self.messages[-n:] if n < len(self.messages) else self.messages[:]

    def clear(self) -> None:
        self.messages = []
        self.token_count = 0


@dataclass
class ChatResponse:
    content: str
    session_id: str
    message_id: str
    model: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_cache_read: int = 0
    intent: str = ""
    mode_hint: str = ""
    latency_ms: float = 0.0
    error: str = ""

    @property
    def success(self) -> bool:
        return not bool(self.error)
