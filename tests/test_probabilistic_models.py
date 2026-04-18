"""
Tests for BetaBelief, GaussianBelief, BayesianHypothesisTracker,
and the math helper functions.
"""
from __future__ import annotations

import math
import pytest


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

class TestMathHelpers:
    def test_beta_mean_uninformative(self):
        from sovereign.forecasting.probabilistic_models import beta_mean
        assert beta_mean(1.0, 1.0) == pytest.approx(0.5)

    def test_beta_mean_biased(self):
        from sovereign.forecasting.probabilistic_models import beta_mean
        # alpha=8, beta=2  → mean = 8/10 = 0.8
        assert beta_mean(8.0, 2.0) == pytest.approx(0.8)

    def test_beta_variance_uninformative(self):
        from sovereign.forecasting.probabilistic_models import beta_variance
        # Uniform: var = 1*1 / (4*3) = 1/12
        assert beta_variance(1.0, 1.0) == pytest.approx(1 / 12, rel=1e-3)

    def test_beta_variance_decreases_with_more_data(self):
        from sovereign.forecasting.probabilistic_models import beta_variance
        v_low  = beta_variance(1.0, 1.0)
        v_high = beta_variance(100.0, 100.0)
        assert v_high < v_low

    def test_normal_ci_symmetric(self):
        from sovereign.forecasting.probabilistic_models import normal_ci
        lo, hi = normal_ci(0.5, 0.1)
        assert lo < 0.5 < hi
        assert hi - 0.5 == pytest.approx(0.5 - lo, abs=1e-6)

    def test_normal_ci_clamped(self):
        from sovereign.forecasting.probabilistic_models import normal_ci
        lo, hi = normal_ci(0.0, 0.5)
        assert lo >= 0.0

    def test_sigmoid_midpoint(self):
        from sovereign.forecasting.probabilistic_models import sigmoid
        assert sigmoid(0.0) == pytest.approx(0.5)

    def test_sigmoid_increases(self):
        from sovereign.forecasting.probabilistic_models import sigmoid
        assert sigmoid(1.0) > sigmoid(0.0)
        assert sigmoid(-1.0) < sigmoid(0.0)

    def test_log_odds_at_half(self):
        from sovereign.forecasting.probabilistic_models import log_odds
        assert log_odds(0.5) == pytest.approx(0.0, abs=1e-6)

    def test_log_odds_above_half_positive(self):
        from sovereign.forecasting.probabilistic_models import log_odds
        assert log_odds(0.8) > 0.0

    def test_log_odds_below_half_negative(self):
        from sovereign.forecasting.probabilistic_models import log_odds
        assert log_odds(0.2) < 0.0


# ---------------------------------------------------------------------------
# BetaBelief
# ---------------------------------------------------------------------------

class TestBetaBelief:
    def test_uninformative_prior_mean(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.uninformative()
        assert b.mean == pytest.approx(0.5)

    def test_uninformative_prior_params(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.uninformative()
        assert b.alpha == pytest.approx(1.0)
        assert b.beta  == pytest.approx(1.0)

    def test_update_successes_moves_mean_up(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.uninformative()
        initial_mean = b.mean
        for _ in range(10):
            b.update(success=True)
        assert b.mean > initial_mean

    def test_update_failures_moves_mean_down(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.uninformative()
        initial_mean = b.mean
        for _ in range(10):
            b.update(success=False)
        assert b.mean < initial_mean

    def test_credible_interval_uninformative_is_wide(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.uninformative()
        lo, hi = b.credible_interval()
        # Should span a large range with only a uniform prior
        assert hi - lo > 0.3

    def test_credible_interval_narrows_with_data(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.uninformative()
        lo0, hi0 = b.credible_interval()
        b.update_batch(successes=50, failures=50)
        lo1, hi1 = b.credible_interval()
        assert (hi1 - lo1) < (hi0 - lo0)

    def test_informed_prior_sets_mean(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.informed(prior_mean=0.7, strength=20.0)
        assert b.mean == pytest.approx(0.7, abs=0.02)

    def test_update_batch(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.uninformative()
        b.update_batch(successes=8, failures=2)
        assert b.alpha == pytest.approx(9.0)  # 1 prior + 8
        assert b.beta  == pytest.approx(3.0)  # 1 prior + 2

    def test_history_recorded(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.uninformative()
        b.update(True)
        b.update(False)
        b.update(True)
        assert len(b.history) == 3
        assert b.history.count(True) == 2

    def test_to_dict_shape(self):
        from sovereign.forecasting.probabilistic_models import BetaBelief
        b = BetaBelief.uninformative(label="test")
        d = b.to_dict()
        for key in ("label", "alpha", "beta", "mean", "std", "mode", "ci_95", "n_observations"):
            assert key in d
        assert d["label"] == "test"


# ---------------------------------------------------------------------------
# GaussianBelief
# ---------------------------------------------------------------------------

class TestGaussianBelief:
    def test_single_update_sets_mean(self):
        from sovereign.forecasting.probabilistic_models import GaussianBelief
        g = GaussianBelief(label="test")
        g.update(42.0)
        assert g.mean == pytest.approx(42.0)

    def test_multiple_updates_converge_to_true_mean(self):
        from sovereign.forecasting.probabilistic_models import GaussianBelief
        import random
        rng = random.Random(42)
        g = GaussianBelief()
        true_mean = 100.0
        for _ in range(1000):
            g.update(true_mean + rng.gauss(0, 10))
        assert g.mean == pytest.approx(true_mean, abs=1.5)

    def test_variance_zero_with_one_observation(self):
        from sovereign.forecasting.probabilistic_models import GaussianBelief
        g = GaussianBelief()
        g.update(5.0)
        assert g.variance == 0.0

    def test_confidence_interval_contains_mean(self):
        from sovereign.forecasting.probabilistic_models import GaussianBelief
        g = GaussianBelief()
        for x in [10.0, 20.0, 30.0, 40.0]:
            g.update(x)
        lo, hi = g.confidence_interval()
        assert lo < g.mean < hi

    def test_n_increments_with_each_update(self):
        from sovereign.forecasting.probabilistic_models import GaussianBelief
        g = GaussianBelief()
        for i in range(5):
            g.update(float(i))
        assert g.n == 5

    def test_to_dict_shape(self):
        from sovereign.forecasting.probabilistic_models import GaussianBelief
        g = GaussianBelief(label="latency")
        g.update(100.0)
        g.update(120.0)
        d = g.to_dict()
        for key in ("label", "n", "mean", "std", "ci_95"):
            assert key in d


# ---------------------------------------------------------------------------
# BayesianHypothesisTracker
# ---------------------------------------------------------------------------

class TestBayesianHypothesisTracker:
    def _tracker_with_two(self):
        from sovereign.forecasting.probabilistic_models import (
            BayesianHypothesisTracker, Hypothesis
        )
        tracker = BayesianHypothesisTracker()
        tracker.add(Hypothesis(
            hypothesis_id="h1", description="Cashflow will improve",
            prior=0.6, likelihood_true=0.8, likelihood_false=0.2,
        ))
        tracker.add(Hypothesis(
            hypothesis_id="h2", description="Cashflow will worsen",
            prior=0.4, likelihood_true=0.3, likelihood_false=0.7,
        ))
        return tracker

    def test_add_hypotheses(self):
        tracker = self._tracker_with_two()
        assert len(tracker._hypotheses) == 2

    def test_posteriors_sum_to_one_after_update(self):
        tracker = self._tracker_with_two()
        tracker.update(evidence_true=True)
        total = sum(h.posterior for h in tracker._hypotheses.values())
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_update_positive_evidence_raises_high_likelihood_hypothesis(self):
        tracker = self._tracker_with_two()
        before_h1 = tracker._hypotheses["h1"].posterior
        tracker.update(evidence_true=True)
        after_h1 = tracker._hypotheses["h1"].posterior
        # h1 has higher likelihood_true, so it should gain posterior mass
        assert after_h1 >= before_h1

    def test_update_negative_evidence_penalises_high_likelihood(self):
        tracker = self._tracker_with_two()
        tracker.update(evidence_true=False)
        # h2 has higher likelihood of negative evidence — it should gain
        assert tracker._hypotheses["h2"].posterior > tracker._hypotheses["h1"].posterior

    def test_top_returns_highest_posterior(self):
        tracker = self._tracker_with_two()
        tracker.update(evidence_true=True)
        tops = tracker.top(n=1)
        assert len(tops) == 1
        assert tops[0].hypothesis_id == "h1"

    def test_to_dict_shape(self):
        tracker = self._tracker_with_two()
        d = tracker.to_dict()
        assert isinstance(d, list)
        for entry in d:
            for key in ("id", "description", "prior", "posterior"):
                assert key in entry

    def test_multiple_updates_stable(self):
        """Running many updates should keep posteriors summing to ~1."""
        tracker = self._tracker_with_two()
        for i in range(20):
            tracker.update(evidence_true=(i % 2 == 0))
        total = sum(h.posterior for h in tracker._hypotheses.values())
        assert total == pytest.approx(1.0, abs=1e-6)
