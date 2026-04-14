"""Experiment registry — tracks A/B tests, prompt variants, and evaluation runs."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Experiment:
    """Metadata for a tracked experiment."""
    name: str
    description: str
    variants: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    status: str = "running"   # "running" | "completed" | "archived"
    created_at: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z"
    )


class ExperimentRegistry:
    """Store and retrieve experiment definitions and results."""

    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}

    def register(self, experiment: Experiment) -> None:
        self._experiments[experiment.name] = experiment

    def get(self, name: str) -> Experiment:
        return self._experiments[name]

    def record_metric(self, name: str, key: str, value: Any) -> None:
        """Record a metric result for an experiment."""
        if name in self._experiments:
            self._experiments[name].metrics[key] = value

    def list_experiments(self) -> list[str]:
        return list(self._experiments)
