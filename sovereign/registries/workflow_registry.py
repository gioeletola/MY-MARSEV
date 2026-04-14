"""Workflow registry — stores named multi-step workflow definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStep:
    """A single step within a workflow."""
    agent_id: str
    objective_template: str     # May contain {variable} placeholders
    tools_allowed: list[str] = field(default_factory=list)
    action_class: str = "SUGGEST"


@dataclass
class WorkflowDefinition:
    """A named, versioned sequence of agent steps."""
    name: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)


class WorkflowRegistry:
    """Stores and retrieves named workflow definitions."""

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}

    def register(self, workflow: WorkflowDefinition) -> None:
        self._workflows[workflow.name] = workflow

    def get(self, name: str) -> WorkflowDefinition:
        try:
            return self._workflows[name]
        except KeyError:
            raise KeyError(f"Workflow '{name}' not found.")

    def list_workflows(self) -> list[str]:
        return list(self._workflows)
