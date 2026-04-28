"""Telemetry data types shared across the telemetry suite."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TelemetryEventType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    AGENT_CALL = "agent_call"
    TOOL_CALL = "tool_call"
    TOKEN_USAGE = "token_usage"
    LATENCY = "latency"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    APPROVAL = "approval"
    CUSTOM = "custom"


@dataclass
class TelemetryEvent:
    """A single discrete telemetry event recorded by the system."""
    event_type: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TelemetryEvent":
        return cls(
            event_id=d.get("event_id", str(uuid.uuid4())),
            event_type=d.get("event_type", "custom"),
            source=d.get("source", "unknown"),
            timestamp=d.get("timestamp", datetime.now(timezone.utc).isoformat()),
            tags=d.get("tags", []),
            data=d.get("data", {}),
        )


@dataclass
class PhaseMetric:
    phase_name: str
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: float = 0.0
    ended_at: float = 0.0
    duration_ms: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_cached: int = 0
    agent_id: str = ""
    model_id: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self, status: PhaseStatus = PhaseStatus.COMPLETED) -> None:
        import time
        self.ended_at = time.time()
        self.duration_ms = (self.ended_at - self.started_at) * 1000
        self.status = status


@dataclass
class SessionTelemetry:
    session_id: str
    started_at: float = field(default_factory=lambda: __import__("time").time())
    ended_at: float = 0.0
    user_input_preview: str = ""
    mode: str = "command"
    phases: list[PhaseMetric] = field(default_factory=list)
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_tokens_cached: int = 0
    total_latency_ms: float = 0.0
    agents_invoked: list[str] = field(default_factory=list)
    models_used: list[str] = field(default_factory=list)
    tool_calls: int = 0
    approval_required: bool = False
    success: bool = True
    error: str | None = None

    def add_phase(self, phase: PhaseMetric) -> None:
        self.phases.append(phase)
        self.total_tokens_input += phase.tokens_input
        self.total_tokens_output += phase.tokens_output
        self.total_tokens_cached += phase.tokens_cached
        if phase.agent_id and phase.agent_id not in self.agents_invoked:
            self.agents_invoked.append(phase.agent_id)
        if phase.model_id and phase.model_id not in self.models_used:
            self.models_used.append(phase.model_id)

    def finish(self, success: bool = True, error: str | None = None) -> None:
        import time
        self.ended_at = time.time()
        self.total_latency_ms = (self.ended_at - self.started_at) * 1000
        self.success = success
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": datetime.fromtimestamp(self.started_at, tz=timezone.utc).isoformat(),
            "ended_at": datetime.fromtimestamp(self.ended_at, tz=timezone.utc).isoformat() if self.ended_at else None,
            "mode": self.mode,
            "user_input_preview": self.user_input_preview[:120],
            "phases_count": len(self.phases),
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "total_tokens_cached": self.total_tokens_cached,
            "cache_hit_rate": (
                self.total_tokens_cached / max(self.total_tokens_input, 1)
            ),
            "total_latency_ms": round(self.total_latency_ms, 1),
            "agents_invoked": self.agents_invoked,
            "models_used": self.models_used,
            "tool_calls": self.tool_calls,
            "approval_required": self.approval_required,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class AggregatedStats:
    period: str  # "hour", "day", "week"
    sessions_total: int = 0
    sessions_success: int = 0
    sessions_failed: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_tokens_cached: int = 0
    avg_cache_hit_rate: float = 0.0
    top_agents: list[tuple[str, int]] = field(default_factory=list)
    top_models: list[tuple[str, int]] = field(default_factory=list)
    approvals_triggered: int = 0
