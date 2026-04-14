"""
Structured output contract for the SOVEREIGN AI OS.

Every agent in the swarm returns a StructuredOutput. This ensures
consistent shape, auditability, and downstream composability across
the entire multi-agent pipeline.
"""
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutputStatus(str, Enum):
    """Lifecycle status of an agent's task execution."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ESCALATED = "escalated"
    PENDING_APPROVAL = "pending_approval"
    SKIPPED = "skipped"


@dataclass
class StructuredOutput:
    """
    14-field standard output contract.

    Every agent in the swarm returns exactly this type.
    Fields are ordered by importance for human review.
    """

    # --- Identity & tracing ---
    session_id: str                                         # 1. Session identifier
    agent_id: str                                           # 2. Producing agent
    task_id: str                                            # 3. Task this output answers

    # --- Status ---
    status: OutputStatus                                    # 4. Lifecycle status

    # --- Primary payload ---
    result: str                                             # 5. Human-readable answer/output

    # --- Structured data ---
    data: dict[str, Any] = field(default_factory=dict)     # 6. Structured data payload

    # --- Reasoning & audit ---
    reasoning: str = ""                                     # 7. Internal reasoning trace
    actions_taken: list[dict[str, Any]] = field(           # 8. Side effects performed
        default_factory=list
    )

    # --- Downstream work ---
    sub_tasks: list[str] = field(default_factory=list)     # 9. Follow-up task IDs spawned
    memory_updates: list[dict[str, Any]] = field(          # 10. Memory writes triggered
        default_factory=list
    )

    # --- Quality & cost ---
    confidence: float = 0.0                                 # 11. 0.0–1.0
    tokens_used: dict[str, int] = field(                   # 12. Token breakdown
        default_factory=lambda: {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
        }
    )

    # --- Timestamps ---
    completed_at: str = field(                             # 13. ISO-8601 UTC timestamp
        default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z"
    )

    # --- Human review flag ---
    requires_human_review: bool = False                    # 14. Escalation trigger

    # --- Internal: error detail (not part of the 14 public fields) ---
    error: str = ""

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (JSON-safe values only)."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "data": self.data,
            "reasoning": self.reasoning,
            "actions_taken": self.actions_taken,
            "sub_tasks": self.sub_tasks,
            "memory_updates": self.memory_updates,
            "confidence": self.confidence,
            "tokens_used": self.tokens_used,
            "completed_at": self.completed_at,
            "requires_human_review": self.requires_human_review,
            "error": self.error,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def add_tokens(self, usage: dict[str, int]) -> None:
        """Accumulate token counts from a Claude API usage object."""
        for key in ("input", "output", "cache_read", "cache_write"):
            self.tokens_used[key] = self.tokens_used.get(key, 0) + usage.get(key, 0)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def failure(
        cls,
        session_id: str,
        agent_id: str,
        task_id: str,
        error: str,
        requires_human_review: bool = False,
    ) -> StructuredOutput:
        """Create a failure output with a minimal footprint."""
        return cls(
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            status=OutputStatus.FAILED,
            result=f"Task failed: {error}",
            error=error,
            requires_human_review=requires_human_review,
        )

    @classmethod
    def escalated(
        cls,
        session_id: str,
        agent_id: str,
        task_id: str,
        reason: str,
    ) -> StructuredOutput:
        """Create an output that signals escalation to human authority."""
        return cls(
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            status=OutputStatus.ESCALATED,
            result=f"Escalated to human authority: {reason}",
            requires_human_review=True,
        )

    @classmethod
    def pending(
        cls,
        session_id: str,
        agent_id: str,
        task_id: str,
        reason: str,
    ) -> StructuredOutput:
        """Create an output waiting for approval before proceeding."""
        return cls(
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            status=OutputStatus.PENDING_APPROVAL,
            result=f"Awaiting approval: {reason}",
            requires_human_review=True,
        )
