"""Goal monitor — tracks progress toward user-defined goals and surfaces alerts."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path("data/memory/goals.json")


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class Goal:
    goal_id: str
    title: str
    description: str
    target_value: float
    current_value: float = 0.0
    unit: str = ""
    deadline: float = 0.0
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)

    @property
    def progress_pct(self) -> float:
        if self.target_value == 0:
            return 0.0
        return min(100.0, (self.current_value / self.target_value) * 100)

    @property
    def is_overdue(self) -> bool:
        return self.deadline > 0 and time.time() > self.deadline and self.status == GoalStatus.ACTIVE


class GoalMonitor:
    def __init__(self) -> None:
        self._goals: dict[str, Goal] = {}
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if _DATA_FILE.exists():
            try:
                raw = json.loads(_DATA_FILE.read_text())
                for g in raw:
                    g["status"] = GoalStatus(g.get("status", "active"))
                    goal = Goal(**g)
                    self._goals[goal.goal_id] = goal
            except Exception:
                pass

    def _save(self) -> None:
        data = [{**g.__dict__, "status": g.status.value} for g in self._goals.values()]
        _DATA_FILE.write_text(json.dumps(data, indent=2))

    def add(self, goal: Goal) -> None:
        self._goals[goal.goal_id] = goal
        self._save()

    def update_progress(self, goal_id: str, value: float) -> Goal | None:
        goal = self._goals.get(goal_id)
        if not goal:
            return None
        goal.current_value = value
        goal.updated_at = time.time()
        if goal.current_value >= goal.target_value:
            goal.status = GoalStatus.COMPLETED
        self._save()
        return goal

    def complete(self, goal_id: str) -> bool:
        goal = self._goals.get(goal_id)
        if goal:
            goal.status = GoalStatus.COMPLETED
            self._save()
            return True
        return False

    def active_goals(self) -> list[Goal]:
        return [g for g in self._goals.values() if g.status == GoalStatus.ACTIVE]

    def overdue_goals(self) -> list[Goal]:
        return [g for g in self._goals.values() if g.is_overdue]

    def at_risk_goals(self, pct_threshold: float = 25.0) -> list[Goal]:
        active = self.active_goals()
        return [g for g in active if g.progress_pct < pct_threshold and g.deadline > 0]

    def summary(self) -> dict:
        all_goals = list(self._goals.values())
        return {
            "total": len(all_goals),
            "active": sum(1 for g in all_goals if g.status == GoalStatus.ACTIVE),
            "completed": sum(1 for g in all_goals if g.status == GoalStatus.COMPLETED),
            "overdue": len(self.overdue_goals()),
        }
