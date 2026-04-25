"""Capability gap detector — identifies tasks that no existing agent handles well."""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_GAPS_PATH = pathlib.Path("data/memory/capability_gaps.json")


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

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_GAPS_PATH) -> None:
        self._failures: list[dict] = []
        self._gaps: dict[str, CapabilityGap] = {}
        self._data_path = pathlib.Path(data_path)
        self._load()

    def record_failure(self, task_objective: str, agent_id: str, error: str) -> None:
        self._failures.append({
            "objective": task_objective,
            "agent_id": agent_id,
            "error": error,
        })
        self._analyse_gap(task_objective)
        self._persist()

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

    def list_gaps(self) -> list[CapabilityGap]:
        """Return all gaps sorted by priority descending."""
        return sorted(self._gaps.values(), key=lambda g: g.priority, reverse=True)

    def get_top_suggestions(self, n: int = 5) -> list[dict[str, Any]]:
        """Return top N gaps as suggested agent blueprints."""
        top = sorted(
            self._gaps.values(),
            key=lambda g: g.priority * g.frequency,
            reverse=True,
        )[:n]
        return [
            {
                "gap_id": g.gap_id,
                "description": g.description,
                "suggested_agent_id": g.suggested_agent_id,
                "suggested_tools": g.suggested_tools,
                "priority": g.priority,
                "frequency": g.frequency,
                "example_tasks": g.example_tasks[:3],
                "blueprint": (
                    f"NewAgent = _make_worker(\n"
                    f"    \"{g.suggested_agent_id}\",\n"
                    f"    \"{g.description[:60]}\",\n"
                    f"    \"Handles: {g.description}\",\n"
                    f"    tools={g.suggested_tools or ['memory_tool']},\n"
                    f")"
                ),
            }
            for g in top
        ]

    def schedule_weekly(self, scheduler: Any) -> None:
        """Register a weekly gap analysis job with the scheduler."""
        from sovereign.infra.scheduler import ScheduleFrequency
        existing = {j.name for j in scheduler.list_jobs()}
        if "weekly_gap_analysis" not in existing:
            scheduler.schedule(
                "weekly_gap_analysis",
                "capability_gap_detector",
                "Run weekly capability gap analysis and generate agent blueprints.",
                ScheduleFrequency.WEEKLY,
            )
            logger.info("CapabilityGapDetector: weekly analysis job registered")

    def _persist(self) -> None:
        """Save current gaps to JSON file."""
        try:
            self._data_path.parent.mkdir(parents=True, exist_ok=True)
            data = {gid: asdict(gap) for gid, gap in self._gaps.items()}
            self._data_path.write_text(
                json.dumps(data, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("CapabilityGapDetector._persist failed: %s", exc)

    def _load(self) -> None:
        """Load persisted gaps from JSON file."""
        if not self._data_path.exists():
            return
        try:
            raw = json.loads(self._data_path.read_text("utf-8"))
            for gid, gdata in raw.items():
                self._gaps[gid] = CapabilityGap(**gdata)
            logger.info(
                "CapabilityGapDetector: loaded %d gaps", len(self._gaps)
            )
        except Exception as exc:
            logger.warning("CapabilityGapDetector._load failed: %s", exc)


# ---------------------------------------------------------------------------
# WeeklyGapReport
# ---------------------------------------------------------------------------

class WeeklyGapReport:
    """Generates a weekly report of top capability gaps sorted by priority * frequency."""

    def generate(self, gaps: list[CapabilityGap]) -> list[dict[str, Any]]:
        """
        Returns a sorted list of top gaps by composite score (priority * frequency),
        highest first.
        """
        sorted_gaps = sorted(
            gaps,
            key=lambda g: g.priority * g.frequency,
            reverse=True,
        )
        return [
            {
                "gap_id": g.gap_id,
                "description": g.description,
                "priority": g.priority,
                "frequency": g.frequency,
                "composite_score": round(g.priority * g.frequency, 3),
                "suggested_agent_id": g.suggested_agent_id,
                "suggested_tools": g.suggested_tools,
                "example_tasks": g.example_tasks[:3],
            }
            for g in sorted_gaps
        ]
