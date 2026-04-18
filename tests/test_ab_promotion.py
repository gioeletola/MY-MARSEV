"""Tests for ExperimentRegistry A/B auto-promotion methods."""
from __future__ import annotations

from sovereign.registries.experiment_registry import Experiment, ExperimentRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_with_experiment(variants: list[str] | None = None) -> tuple[ExperimentRegistry, str]:
    """Return (registry, exp_id) with a single running experiment registered."""
    reg = ExperimentRegistry()
    exp = Experiment(
        name="test_exp_01",
        description="Test experiment",
        variants=variants or ["control", "variant_a"],
    )
    reg.register(exp)
    return reg, exp.name


# ---------------------------------------------------------------------------
# record_response
# ---------------------------------------------------------------------------


class TestRecordResponse:
    def test_adds_to_beliefs_dict(self):
        reg, exp_id = _make_registry_with_experiment()
        reg.record_response(exp_id, "control", True)
        assert exp_id in reg._beliefs
        assert "control" in reg._beliefs[exp_id]

    def test_initialises_uninformative_prior(self):
        reg, exp_id = _make_registry_with_experiment()
        reg.record_response(exp_id, "control", True)
        belief = reg._beliefs[exp_id]["control"]
        # After one success on uniform prior: alpha=2, beta=1
        assert belief.alpha == 2.0
        assert belief.beta == 1.0

    def test_updates_multiple_variants(self):
        reg, exp_id = _make_registry_with_experiment()
        reg.record_response(exp_id, "control", True)
        reg.record_response(exp_id, "variant_a", False)
        assert "control" in reg._beliefs[exp_id]
        assert "variant_a" in reg._beliefs[exp_id]

    def test_accumulates_observations(self):
        reg, exp_id = _make_registry_with_experiment()
        for _ in range(5):
            reg.record_response(exp_id, "control", True)
        belief = reg._beliefs[exp_id]["control"]
        # 5 successes on uniform prior → alpha=6
        assert belief.alpha == 6.0

    def test_failure_updates_beta(self):
        reg, exp_id = _make_registry_with_experiment()
        reg.record_response(exp_id, "control", False)
        belief = reg._beliefs[exp_id]["control"]
        # 1 failure on uniform prior → beta=2
        assert belief.beta == 2.0

    def test_creates_separate_belief_per_experiment(self):
        reg = ExperimentRegistry()
        reg.register(Experiment(name="exp_a", description="a", variants=["c", "v"]))
        reg.register(Experiment(name="exp_b", description="b", variants=["c", "v"]))
        reg.record_response("exp_a", "c", True)
        reg.record_response("exp_b", "c", False)
        assert reg._beliefs["exp_a"]["c"].alpha == 2.0
        assert reg._beliefs["exp_b"]["c"].beta == 2.0


# ---------------------------------------------------------------------------
# auto_promote_winners
# ---------------------------------------------------------------------------


class TestAutoPromoteWinners:
    def test_returns_list(self):
        reg, _ = _make_registry_with_experiment()
        result = reg.auto_promote_winners()
        assert isinstance(result, list)

    def test_no_promotion_with_few_samples(self):
        reg, exp_id = _make_registry_with_experiment()
        # Only 10 samples — well below min_samples=100
        for _ in range(10):
            reg.record_response(exp_id, "control", True)
        for _ in range(10):
            reg.record_response(exp_id, "variant_a", True)
        result = reg.auto_promote_winners(min_samples=100)
        assert result == []

    def test_no_promotion_when_lift_insufficient(self):
        reg, exp_id = _make_registry_with_experiment()
        # Both variants at ~50% — no lift
        for _ in range(100):
            reg.record_response(exp_id, "control", True)
        for _ in range(100):
            reg.record_response(exp_id, "control", False)
        for _ in range(100):
            reg.record_response(exp_id, "variant_a", True)
        for _ in range(100):
            reg.record_response(exp_id, "variant_a", False)
        result = reg.auto_promote_winners(min_samples=100, min_improvement=0.05)
        assert result == []

    def test_promotes_when_lift_and_samples_met(self):
        reg, exp_id = _make_registry_with_experiment()
        # Control at ~50%, variant_a at ~80% — clear lift
        for _ in range(50):
            reg.record_response(exp_id, "control", True)
        for _ in range(50):
            reg.record_response(exp_id, "control", False)
        for _ in range(80):
            reg.record_response(exp_id, "variant_a", True)
        for _ in range(20):
            reg.record_response(exp_id, "variant_a", False)
        result = reg.auto_promote_winners(min_samples=100, min_improvement=0.05)
        assert len(result) == 1
        assert result[0]["exp_id"] == exp_id
        assert result[0]["winner_variant_id"] == "variant_a"
        assert result[0]["lift"] > 0.05

    def test_promoted_result_has_required_keys(self):
        reg, exp_id = _make_registry_with_experiment()
        for _ in range(50):
            reg.record_response(exp_id, "control", True)
        for _ in range(50):
            reg.record_response(exp_id, "control", False)
        for _ in range(90):
            reg.record_response(exp_id, "variant_a", True)
        for _ in range(10):
            reg.record_response(exp_id, "variant_a", False)
        result = reg.auto_promote_winners(min_samples=100, min_improvement=0.05)
        assert len(result) == 1
        rec = result[0]
        assert "exp_id" in rec
        assert "winner_variant_id" in rec
        assert "lift" in rec
        assert "promoted_at" in rec

    def test_marks_experiment_status_promoted(self):
        reg, exp_id = _make_registry_with_experiment()
        for _ in range(50):
            reg.record_response(exp_id, "control", True)
        for _ in range(50):
            reg.record_response(exp_id, "control", False)
        for _ in range(90):
            reg.record_response(exp_id, "variant_a", True)
        for _ in range(10):
            reg.record_response(exp_id, "variant_a", False)
        reg.auto_promote_winners(min_samples=100, min_improvement=0.05)
        assert reg.get(exp_id).status == "promoted"

    def test_does_not_promote_completed_experiment(self):
        reg, exp_id = _make_registry_with_experiment()
        reg.get(exp_id).status = "completed"
        for _ in range(200):
            reg.record_response(exp_id, "variant_a", True)
        result = reg.auto_promote_winners(min_samples=100, min_improvement=0.0)
        assert result == []

    def test_does_not_promote_already_promoted_experiment(self):
        reg, exp_id = _make_registry_with_experiment()
        reg.get(exp_id).status = "promoted"
        for _ in range(200):
            reg.record_response(exp_id, "variant_a", True)
        result = reg.auto_promote_winners(min_samples=100, min_improvement=0.0)
        assert result == []

    def test_lift_value_is_positive_on_promotion(self):
        reg, exp_id = _make_registry_with_experiment()
        for _ in range(50):
            reg.record_response(exp_id, "control", True)
        for _ in range(50):
            reg.record_response(exp_id, "control", False)
        for _ in range(90):
            reg.record_response(exp_id, "variant_a", True)
        for _ in range(10):
            reg.record_response(exp_id, "variant_a", False)
        result = reg.auto_promote_winners(min_samples=100, min_improvement=0.05)
        assert result[0]["lift"] > 0

    def test_no_beliefs_registered_returns_empty(self):
        reg, _ = _make_registry_with_experiment()
        result = reg.auto_promote_winners()
        assert result == []

    def test_custom_min_improvement_threshold(self):
        reg, exp_id = _make_registry_with_experiment()
        # Small lift ~10%
        for _ in range(50):
            reg.record_response(exp_id, "control", True)
        for _ in range(50):
            reg.record_response(exp_id, "control", False)
        for _ in range(60):
            reg.record_response(exp_id, "variant_a", True)
        for _ in range(40):
            reg.record_response(exp_id, "variant_a", False)
        # With high threshold: no promotion
        r1 = reg.auto_promote_winners(min_samples=100, min_improvement=0.20)
        assert r1 == []
        # Reset status for re-test with lower threshold
        reg.get(exp_id).status = "running"
        r2 = reg.auto_promote_winners(min_samples=100, min_improvement=0.05)
        assert len(r2) == 1
