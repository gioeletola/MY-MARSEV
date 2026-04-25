"""Memory domain: health_routine — health metrics, routines, habits, biomarkers."""
from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_DATA_FILE = pathlib.Path("data/memory/health_routine.json")
DOMAIN_NAME = "health_routine"


@dataclass
class HealthMetric:
    metric_id: str
    metric_type: str            # weight | sleep | steps | heart_rate | bp | glucose | mood | energy
    value: float = 0.0
    unit: str = ""
    recorded_at: str = ""
    source: str = "manual"      # manual | wearable | app
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Routine:
    routine_id: str
    name: str
    frequency: str = "daily"    # daily | weekly | monthly
    time_of_day: str = "morning"
    duration_minutes: int = 30
    steps: list[str] = field(default_factory=list)
    active: bool = True
    tags: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HealthProfile:
    age: int = 0
    height_cm: float = 0.0
    weight_kg: float = 0.0
    blood_type: str = ""
    conditions: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    fitness_level: str = "moderate"    # sedentary | light | moderate | active | athlete
    sleep_goal_hours: float = 8.0
    water_goal_ml: float = 2000.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HealthRoutineMemoryStore:
    def __init__(self, data_file: pathlib.Path = _DATA_FILE) -> None:
        self._path = data_file
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except Exception:
                pass
        return {"profile": {}, "metrics": [], "routines": {}}

    def _save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, default=str))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_profile(self) -> HealthProfile:
        return HealthProfile(**{
            k: v for k, v in self._data.get("profile", {}).items()
            if k in HealthProfile.__dataclass_fields__
        })

    def update_profile(self, **kwargs: Any) -> None:
        self._data.setdefault("profile", {}).update(kwargs)
        self._save()

    def log_metric(self, metric: HealthMetric) -> None:
        if not metric.recorded_at:
            metric.recorded_at = self._now()
        self._data.setdefault("metrics", []).append(metric.to_dict())
        self._save()

    def recent_metrics(self, metric_type: str | None = None, n: int = 10) -> list[HealthMetric]:
        metrics = self._data.get("metrics", [])
        if metric_type:
            metrics = [m for m in metrics if m.get("metric_type") == metric_type]
        metrics = sorted(metrics, key=lambda m: m.get("recorded_at", ""), reverse=True)
        return [
            HealthMetric(**{k: v for k, v in m.items() if k in HealthMetric.__dataclass_fields__})
            for m in metrics[:n]
        ]

    def add_routine(self, routine: Routine) -> None:
        if not routine.created_at:
            routine.created_at = self._now()
        self._data.setdefault("routines", {})[routine.routine_id] = routine.to_dict()
        self._save()

    def active_routines(self) -> list[Routine]:
        return [
            Routine(**{k: v for k, v in r.items() if k in Routine.__dataclass_fields__})
            for r in self._data.get("routines", {}).values()
            if r.get("active", True)
        ]

    def to_context_string(self) -> str:
        profile = self.get_profile()
        routines = self.active_routines()
        parts = []
        if profile.fitness_level:
            parts.append(f"Fitness: {profile.fitness_level}")
        if routines:
            parts.append(f"Active routines: {len(routines)}")
        return " | ".join(parts) if parts else "Health profile not configured."


store = HealthRoutineMemoryStore()
