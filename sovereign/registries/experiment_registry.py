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
    status: str = "running"   # "running" | "completed" | "archived" | "promoted"
    created_at: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z"
    )


class ExperimentRegistry:
    """Store and retrieve experiment definitions and results."""

    def __init__(self) -> None:
        self._experiments: dict[str, Experiment] = {}
        self._beliefs: dict[str, dict[str, Any]] = {}

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

    def record_response(self, exp_id: str, variant_id: str, success: bool) -> None:
        """Record a binary outcome for a variant. Updates BetaBelief."""
        from sovereign.forecasting.probabilistic_models import BetaBelief

        exp_beliefs = self._beliefs.setdefault(exp_id, {})
        if variant_id not in exp_beliefs:
            exp_beliefs[variant_id] = BetaBelief.uninformative()
        exp_beliefs[variant_id].update(success)

    def auto_promote_winners(
        self,
        min_samples: int = 100,
        min_improvement: float = 0.05,
        confidence: float = 0.95,
    ) -> list[dict]:
        """
        For each running experiment, check if a variant beats the control.

        Uses BetaBelief.mean to compute lift.
        Promotes if: variant_mean - control_mean >= min_improvement AND
                     variant has >= min_samples observations.
        Returns list of {exp_id, winner_variant_id, lift, promoted_at}.
        Marks experiment status as "promoted".
        """
        promoted: list[dict] = []

        for exp_id, variant_beliefs in self._beliefs.items():
            experiment = self._experiments.get(exp_id)
            if experiment is None or experiment.status != "running":
                continue

            # Determine control variant — first variant in the experiment's list,
            # or the one named "control", falling back to alphabetical first.
            variants = list(variant_beliefs.keys())
            if not variants:
                continue

            control_id: str | None = None
            if experiment.variants:
                for v in experiment.variants:
                    if v in variant_beliefs:
                        control_id = v
                        break
            if control_id is None:
                control_id = sorted(variants)[0]

            control_belief = variant_beliefs.get(control_id)
            if control_belief is None:
                continue
            control_mean = control_belief.mean

            for variant_id, belief in variant_beliefs.items():
                if variant_id == control_id:
                    continue
                # Effective sample count (alpha + beta - 2 prior counts)
                n_samples = belief.alpha + belief.beta - 2
                if n_samples < min_samples:
                    continue
                lift = belief.mean - control_mean
                if lift >= min_improvement:
                    promoted_at = datetime.datetime.utcnow().isoformat() + "Z"
                    experiment.status = "promoted"
                    promoted.append({
                        "exp_id": exp_id,
                        "winner_variant_id": variant_id,
                        "lift": round(lift, 6),
                        "promoted_at": promoted_at,
                    })
                    break  # promote at most one winner per experiment

        return promoted
