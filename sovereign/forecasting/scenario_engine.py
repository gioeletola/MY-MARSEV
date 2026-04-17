"""Scenario engine — generates and evaluates what-if scenarios."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    scenario_id: str
    name: str
    description: str
    assumptions: dict[str, Any] = field(default_factory=dict)
    outcomes: dict[str, Any] = field(default_factory=dict)
    probability: float = 0.5
    impact: str = "medium"  # low / medium / high / critical
    time_horizon_days: int = 90
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)


@dataclass
class ScenarioComparison:
    baseline: Scenario
    alternatives: list[Scenario]
    recommended: str
    rationale: str
    confidence: float = 0.7


class ScenarioEngine:
    def __init__(self) -> None:
        self._scenarios: dict[str, Scenario] = {}

    def create(self, scenario: Scenario) -> Scenario:
        self._scenarios[scenario.scenario_id] = scenario
        return scenario

    def get(self, scenario_id: str) -> Scenario | None:
        return self._scenarios.get(scenario_id)

    def list_all(self) -> list[Scenario]:
        return list(self._scenarios.values())

    def compare(self, baseline_id: str, alternative_ids: list[str]) -> ScenarioComparison | None:
        baseline = self._scenarios.get(baseline_id)
        if not baseline:
            return None
        alternatives = [self._scenarios[aid] for aid in alternative_ids if aid in self._scenarios]
        if not alternatives:
            return None
        best = max([baseline] + alternatives, key=lambda s: s.probability * (1.0 if s.impact != "critical" else 0.3))
        return ScenarioComparison(
            baseline=baseline,
            alternatives=alternatives,
            recommended=best.scenario_id,
            rationale=f"Highest risk-adjusted probability: {best.probability:.0%}",
            confidence=0.65,
        )

    def high_impact_scenarios(self) -> list[Scenario]:
        return [s for s in self._scenarios.values() if s.impact in ("high", "critical")]

    def by_probability(self, min_p: float = 0.5) -> list[Scenario]:
        return sorted(
            [s for s in self._scenarios.values() if s.probability >= min_p],
            key=lambda s: s.probability, reverse=True
        )
