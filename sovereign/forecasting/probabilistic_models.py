"""Probabilistic models — Bayesian updates, Beta distributions, confidence intervals."""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core math helpers (no external deps)
# ---------------------------------------------------------------------------

def beta_mean(alpha: float, beta: float) -> float:
    """E[X] for Beta(alpha, beta)."""
    return alpha / (alpha + beta)


def beta_variance(alpha: float, beta: float) -> float:
    """Var[X] for Beta(alpha, beta)."""
    s = alpha + beta
    return (alpha * beta) / (s * s * (s + 1))


def beta_std(alpha: float, beta: float) -> float:
    return math.sqrt(beta_variance(alpha, beta))


def beta_mode(alpha: float, beta: float) -> float:
    """Mode of Beta(alpha, beta) — undefined for alpha,beta < 1."""
    if alpha > 1 and beta > 1:
        return (alpha - 1) / (alpha + beta - 2)
    return 0.5


def normal_ci(mean: float, std: float, z: float = 1.96) -> tuple[float, float]:
    """Normal 95% confidence interval (z=1.96 by default)."""
    margin = z * std
    return max(0.0, mean - margin), min(1.0, mean + margin)


def log_odds(p: float) -> float:
    p = max(1e-9, min(1 - 1e-9, p))
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# Beta-Bernoulli belief (conjugate prior for binary outcomes)
# ---------------------------------------------------------------------------

@dataclass
class BetaBelief:
    """
    Bayesian belief about a probability p, using Beta(alpha, beta) as prior.

    Usage::
        belief = BetaBelief.uninformative()
        belief.update(success=True)   # e.g. prediction was correct
        belief.update(success=False)  # prediction was wrong
        print(belief.mean, belief.credible_interval())
    """
    alpha: float = 1.0    # pseudo-successes (prior + observations)
    beta:  float = 1.0    # pseudo-failures
    label: str = ""
    history: list[bool] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def uninformative(cls, label: str = "") -> "BetaBelief":
        """Uniform prior: no information, p ~ Uniform(0,1)."""
        return cls(alpha=1.0, beta=1.0, label=label)

    @classmethod
    def informed(cls, prior_mean: float, strength: float = 10.0, label: str = "") -> "BetaBelief":
        """Informative prior centred at prior_mean with given pseudo-count strength."""
        a = prior_mean * strength
        b = (1 - prior_mean) * strength
        return cls(alpha=max(0.01, a), beta=max(0.01, b), label=label)

    def update(self, success: bool, weight: float = 1.0) -> None:
        """Bayesian update on a single Bernoulli observation."""
        if success:
            self.alpha += weight
        else:
            self.beta += weight
        self.history.append(success)
        self.updated_at = time.time()

    def update_batch(self, successes: int, failures: int) -> None:
        self.alpha += successes
        self.beta  += failures
        self.history.extend([True] * successes + [False] * failures)
        self.updated_at = time.time()

    @property
    def mean(self) -> float:
        return beta_mean(self.alpha, self.beta)

    @property
    def std(self) -> float:
        return beta_std(self.alpha, self.beta)

    @property
    def mode(self) -> float:
        return beta_mode(self.alpha, self.beta)

    @property
    def n(self) -> float:
        return self.alpha + self.beta - 2  # effective sample size (removing 1+1 prior)

    def credible_interval(self, confidence: float = 0.95) -> tuple[float, float]:
        """Return (lower, upper) credible interval using normal approximation."""
        z = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}.get(confidence, 1.96)
        return normal_ci(self.mean, self.std, z)

    def to_dict(self) -> dict:
        lo, hi = self.credible_interval()
        return {
            "label": self.label, "alpha": round(self.alpha, 4), "beta": round(self.beta, 4),
            "mean": round(self.mean, 4), "std": round(self.std, 4),
            "mode": round(self.mode, 4), "ci_95": [round(lo, 4), round(hi, 4)],
            "n_observations": len(self.history),
        }


# ---------------------------------------------------------------------------
# Gaussian belief (continuous outcomes)
# ---------------------------------------------------------------------------

@dataclass
class GaussianBelief:
    """
    Bayesian running estimate of a Gaussian quantity using Welford's algorithm.

    Useful for tracking e.g. latency, confidence scores, cashflow.
    """
    label: str = ""
    _n:    int   = 0
    _mean: float = 0.0
    _M2:   float = 0.0   # sum of squared deviations
    created_at: float = field(default_factory=time.time)

    def update(self, x: float) -> None:
        self._n  += 1
        delta     = x - self._mean
        self._mean += delta / self._n
        delta2    = x - self._mean
        self._M2 += delta * delta2

    @property
    def mean(self) -> float:
        return self._mean

    @property
    def variance(self) -> float:
        return self._M2 / self._n if self._n >= 2 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    @property
    def n(self) -> int:
        return self._n

    def confidence_interval(self, z: float = 1.96) -> tuple[float, float]:
        se = self.std / math.sqrt(max(1, self._n))
        return self._mean - z * se, self._mean + z * se

    def to_dict(self) -> dict:
        lo, hi = self.confidence_interval()
        return {
            "label": self.label, "n": self._n, "mean": round(self._mean, 4),
            "std": round(self.std, 4), "ci_95": [round(lo, 4), round(hi, 4)],
        }


# ---------------------------------------------------------------------------
# Multi-hypothesis tracker
# ---------------------------------------------------------------------------

@dataclass
class Hypothesis:
    hypothesis_id: str
    description: str
    prior: float = 0.5
    likelihood_true: float  = 0.8   # P(evidence | H true)
    likelihood_false: float = 0.2   # P(evidence | H false)
    posterior: float = field(init=False)

    def __post_init__(self) -> None:
        self.posterior = self.prior


class BayesianHypothesisTracker:
    """
    Tracks multiple competing hypotheses and updates their posteriors
    on new evidence using Bayes' theorem.
    """

    def __init__(self) -> None:
        self._hypotheses: dict[str, Hypothesis] = {}

    def add(self, h: Hypothesis) -> None:
        self._hypotheses[h.hypothesis_id] = h

    def update(self, evidence_true: bool) -> None:
        """
        Update all hypothesis posteriors given one piece of binary evidence.
        Uses the likelihood ratio update and renormalises.
        """
        scores: dict[str, float] = {}
        for hid, h in self._hypotheses.items():
            lh = h.likelihood_true if evidence_true else (1 - h.likelihood_true)
            scores[hid] = h.posterior * lh

        total = sum(scores.values())
        if total == 0:
            return
        for hid, h in self._hypotheses.items():
            h.posterior = scores[hid] / total

    def top(self, n: int = 3) -> list[Hypothesis]:
        return sorted(self._hypotheses.values(), key=lambda h: h.posterior, reverse=True)[:n]

    def to_dict(self) -> list[dict]:
        return [
            {"id": h.hypothesis_id, "description": h.description,
             "prior": round(h.prior, 4), "posterior": round(h.posterior, 4)}
            for h in sorted(self._hypotheses.values(), key=lambda h: h.posterior, reverse=True)
        ]
