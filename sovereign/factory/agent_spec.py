"""AgentSpec — blueprint for spawning an ephemeral sub-agent."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sovereign.kernel.action_classes import ActionClass


@dataclass
class AgentSpec:
    """
    Complete specification for an ephemeral sub-agent.

    All fields should be set by the spawning orchestrator before calling
    AgentFactory.spawn(). Missing fields are flagged by validate().
    """

    name: str                                           # Short unique identifier
    role: str                                           # Human-readable role description
    objective: str                                      # Narrow, specific task objective

    tools: list[str] = field(default_factory=list)      # Tool names the agent may use
    scope: dict[str, Any] = field(default_factory=dict) # Scope constraints (blocked_actions, etc.)
    stop_conditions: list[str] = field(default_factory=list)

    output_schema: dict[str, Any] | None = None         # Optional JSON Schema for result.data

    max_action_class: ActionClass = ActionClass.SUGGEST
    model: str = "claude-haiku-4-5-20251001"            # Default: cheapest model
    max_iterations: int = 5
    ttl_seconds: int = 300                              # Auto-destroy after 5 minutes

    def validate(self) -> None:
        """
        Raise ValueError if the spec is incomplete or contradictory.
        Call before passing to AgentFactory.spawn().
        """
        if not self.name:
            raise ValueError("AgentSpec.name must not be empty.")
        if not self.objective:
            raise ValueError("AgentSpec.objective must not be empty.")
        if self.ttl_seconds < 1:
            raise ValueError(f"AgentSpec.ttl_seconds must be >= 1, got {self.ttl_seconds}.")
        if self.max_iterations < 1:
            raise ValueError(f"AgentSpec.max_iterations must be >= 1, got {self.max_iterations}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "objective": self.objective,
            "tools": self.tools,
            "max_action_class": self.max_action_class.name,
            "model": self.model,
            "max_iterations": self.max_iterations,
            "ttl_seconds": self.ttl_seconds,
        }
