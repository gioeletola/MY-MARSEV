"""Typed event catalogue for SOVEREIGN AI OS."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time


class EventType(str, Enum):
    # Session lifecycle
    SESSION_START     = "session_start"
    SESSION_END       = "session_end"
    # Task execution
    TASK_START        = "task_start"
    TASK_DONE         = "task_done"
    TASK_FAILED       = "task_failed"
    # Agent activity
    AGENT_STEP        = "agent_step"
    TOOL_CALL         = "tool_call"
    TOOL_RESULT       = "tool_result"
    # Mode changes
    MODE_CHANGE       = "mode_change"
    # Memory
    MEMORY_WRITE      = "memory_write"
    MEMORY_READ       = "memory_read"
    # Security / governance
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_RESOLVED = "approval_resolved"
    SECURITY_ALERT    = "security_alert"
    # Streaming tokens
    STREAM_TOKEN      = "stream_token"
    STREAM_DONE       = "stream_done"
    # Health / scheduler
    HEALTH_UPDATE     = "health_update"
    JOB_SCHEDULED     = "job_scheduled"
    JOB_COMPLETE      = "job_complete"
    # Custom / passthrough
    CUSTOM            = "custom"


@dataclass
class SovereignEvent:
    """
    Typed event emitted by the orchestrator and consumed by subscribers.

    All events carry:
      - type: EventType enum value
      - session_id: originating session (empty for system events)
      - ts: Unix timestamp of emission
      - data: event-specific payload dict
    """
    type: EventType
    session_id: str = ""
    ts: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (for WS JSON transport)."""
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "ts": self.ts,
            **self.data,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SovereignEvent":
        """Deserialise from a plain dict."""
        raw_type = d.get("type", "custom")
        try:
            etype = EventType(raw_type)
        except ValueError:
            etype = EventType.CUSTOM
        return cls(
            type=etype,
            session_id=d.get("session_id", ""),
            ts=d.get("ts", time.time()),
            data={k: v for k, v in d.items() if k not in ("type", "session_id", "ts")},
        )
