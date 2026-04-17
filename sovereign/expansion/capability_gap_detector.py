"""Capability gap detector — identifies tasks that no existing agent handles well."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CapabilityGap:
    gap_id: str
    description: str
    example_tasks: list[str] = field(default_factory=list)
    frequency: int = 1
    priority: float = 0.5
    suggested_agent_id: str = ""
    suggested_tools: list[str] = field(default_factory=list)


class CapabilityGapDetector:
    """
    Tracks tasks that agents fail or decline and surfaces capability gaps
    that could be filled by creating new agents.
    """

    def __init__(self) -> None:
        self._failures: list[dict] = []
        self._gaps: dict[str, CapabilityGap] = {}

    def record_failure(self, task_objective: str, agent_id: str, error: str) -> None:
        self._failures.append({
            "objective": task_objective,
            "agent_id": agent_id,
            "error": error,
        })
        self._analyse_gap(task_objective)

    def _analyse_gap(self, objective: str) -> None:
        keywords = objective.lower().split()
        gap_id = "_".join(sorted(set(keywords[:3])))
        if gap_id in self._gaps:
            self._gaps[gap_id].frequency += 1
            self._gaps[gap_id].example_tasks.append(objective)
        else:
            self._gaps[gap_id] = CapabilityGap(
                gap_id=gap_id,
                description=f"No agent handles: '{objective}'",
                example_tasks=[objective],
                frequency=1,
                priority=0.5,
                suggested_agent_id=f"{gap_id}_agent",
            )

    def top_gaps(self, n: int = 5) -> list[CapabilityGap]:
        return sorted(self._gaps.values(), key=lambda g: g.frequency, reverse=True)[:n]

    def all_gaps(self) -> list[CapabilityGap]:
        return list(self._gaps.values())
