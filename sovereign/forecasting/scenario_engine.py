"""Scenario engine — generates and evaluates what-if scenarios."""
from __future__ import annotations

import logging
import math
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Impact level → numeric value for expected-value calculations
_IMPACT_VALUES = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}


@dataclass
class Scenario:
    name: str
    probability: float          # 0.0 – 1.0
    description: str
    impact_level: str = "medium"        # low / medium / high / critical
    timeline_days: int = 90
    assumptions: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)
    # Internal fields
    scenario_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    outcomes: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)

    @property
    def impact_value(self) -> float:
        return _IMPACT_VALUES.get(self.impact_level, 0.5)

    @property
    def expected_value(self) -> float:
        """Probability × impact — primary ranking key."""
        return round(self.probability * self.impact_value, 4)


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

    # ── CRUD ─────────────────────────────────────────────────────────────

    def create(self, scenario: Scenario) -> Scenario:
        self._scenarios[scenario.scenario_id] = scenario
        return scenario

    def get(self, scenario_id: str) -> Scenario | None:
        return self._scenarios.get(scenario_id)

    def list_all(self) -> list[Scenario]:
        return list(self._scenarios.values())

    # ── Core new API ─────────────────────────────────────────────────────

    def run(self, context: dict) -> list[Scenario]:
        """Generate base, optimistic, and pessimistic scenarios from *context*.

        *context* keys used:
          - topic (str)
          - base_probability (float, default 0.5)
          - impact_level (str, default "medium")
          - timeline_days (int, default 90)
          - assumptions (list[str])
          - mitigations (list[str])
        """
        topic = context.get("topic", "Unnamed scenario")
        base_p = float(context.get("base_probability", 0.5))
        impact = context.get("impact_level", "medium")
        days = int(context.get("timeline_days", 90))
        assumptions = list(context.get("assumptions", []))
        mitigations = list(context.get("mitigations", []))

        base = Scenario(
            name=f"{topic} — Base",
            probability=round(max(0.05, min(0.95, base_p)), 3),
            description=f"Most-likely outcome for '{topic}' over {days} days.",
            impact_level=impact,
            timeline_days=days,
            assumptions=assumptions,
            mitigations=mitigations,
            tags=["base"],
        )
        optimistic = Scenario(
            name=f"{topic} — Optimistic",
            probability=round(max(0.05, min(0.95, base_p * 1.3)), 3),
            description=f"Best-case outcome for '{topic}': tailwinds and smooth execution.",
            impact_level=_upgrade_impact(impact),
            timeline_days=days,
            assumptions=[a + " (favourable)" for a in assumptions],
            mitigations=mitigations,
            tags=["optimistic"],
        )
        pessimistic = Scenario(
            name=f"{topic} — Pessimistic",
            probability=round(max(0.05, min(0.95, base_p * 0.6)), 3),
            description=f"Worst-case outcome for '{topic}': headwinds and execution risk.",
            impact_level=_downgrade_impact(impact),
            timeline_days=days,
            assumptions=[a + " (challenged)" for a in assumptions],
            mitigations=[],
            tags=["pessimistic"],
        )
        for s in (base, optimistic, pessimistic):
            self._scenarios[s.scenario_id] = s
        logger.info("ScenarioEngine.run: generated 3 scenarios for '%s'", topic)
        return [base, optimistic, pessimistic]

    def monte_carlo(
        self,
        variable: str,
        mean: float,
        std: float,
        n: int = 1000,
    ) -> dict:
        """Run a Monte Carlo simulation for *variable* using a normal distribution.

        Returns a percentile distribution dict and summary statistics.
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        samples = [random.gauss(mean, std) for _ in range(n)]
        samples.sort()

        def percentile(p: float) -> float:
            idx = int(len(samples) * p / 100)
            idx = min(idx, len(samples) - 1)
            return round(samples[idx], 4)

        total = sum(samples)
        avg = total / n
        variance = sum((x - avg) ** 2 for x in samples) / n
        std_actual = math.sqrt(variance)

        return {
            "variable": variable,
            "n": n,
            "mean": round(avg, 4),
            "std": round(std_actual, 4),
            "min": round(samples[0], 4),
            "max": round(samples[-1], 4),
            "p5": percentile(5),
            "p10": percentile(10),
            "p25": percentile(25),
            "p50": percentile(50),
            "p75": percentile(75),
            "p90": percentile(90),
            "p95": percentile(95),
        }

    # ── Ranking ───────────────────────────────────────────────────────────

    def compare(self, baseline_id: str, alternative_ids: list[str]) -> ScenarioComparison | None:
        baseline = self._scenarios.get(baseline_id)
        if not baseline:
            return None
        alternatives = [self._scenarios[aid] for aid in alternative_ids if aid in self._scenarios]
        if not alternatives:
            return None
        best = max([baseline] + alternatives, key=lambda s: s.expected_value)
        return ScenarioComparison(
            baseline=baseline,
            alternatives=alternatives,
            recommended=best.scenario_id,
            rationale=f"Highest expected value ({best.expected_value:.3f}): probability={best.probability:.0%}, impact={best.impact_level}",
            confidence=0.65,
        )

    def high_impact_scenarios(self) -> list[Scenario]:
        return [s for s in self._scenarios.values() if s.impact_level in ("high", "critical")]

    def by_probability(self, min_p: float = 0.5) -> list[Scenario]:
        return sorted(
            [s for s in self._scenarios.values() if s.probability >= min_p],
            key=lambda s: s.probability, reverse=True
        )


def rank_scenarios(scenarios: list[Scenario]) -> list[Scenario]:
    """Return *scenarios* sorted by expected value (probability × impact), descending."""
    return sorted(scenarios, key=lambda s: s.expected_value, reverse=True)


# ── Helpers ───────────────────────────────────────────────────────────────

_IMPACT_ORDER = ["low", "medium", "high", "critical"]


def _upgrade_impact(level: str) -> str:
    idx = _IMPACT_ORDER.index(level) if level in _IMPACT_ORDER else 1
    return _IMPACT_ORDER[min(idx + 1, len(_IMPACT_ORDER) - 1)]


def _downgrade_impact(level: str) -> str:
    idx = _IMPACT_ORDER.index(level) if level in _IMPACT_ORDER else 1
    return _IMPACT_ORDER[max(idx - 1, 0)]
