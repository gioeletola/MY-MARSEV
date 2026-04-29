"""Tests for the model router and cost estimator."""

from sovereign.router.model_router import MODEL_IDS, ModelRouter, ModelTier, RoutingCriteria
from sovereign.router.cost_estimator import estimate_cost, estimate_from_usage


class TestModelRouter:
    def setup_method(self):
        self.router = ModelRouter()

    def test_complex_task_routes_to_frontier(self):
        criteria = RoutingCriteria(task_complexity=0.9, is_sensitive=False)
        assert self.router.route(criteria) == MODEL_IDS[ModelTier.FRONTIER]

    def test_sensitive_complex_routes_to_frontier(self):
        criteria = RoutingCriteria(task_complexity=0.6, is_sensitive=True)
        assert self.router.route(criteria) == MODEL_IDS[ModelTier.FRONTIER]

    def test_reasoning_routes_to_frontier(self):
        criteria = RoutingCriteria(requires_reasoning=True)
        assert self.router.route(criteria) == MODEL_IDS[ModelTier.FRONTIER]

    def test_tight_latency_routes_to_fast(self):
        criteria = RoutingCriteria(latency_budget_ms=1000, task_complexity=0.4)
        assert self.router.route(criteria) == MODEL_IDS[ModelTier.FAST]

    def test_low_complexity_routes_to_fast(self):
        criteria = RoutingCriteria(task_complexity=0.2)
        assert self.router.route(criteria) == MODEL_IDS[ModelTier.FAST]

    def test_default_routes_to_balanced(self):
        criteria = RoutingCriteria(task_complexity=0.5)
        assert self.router.route(criteria) == MODEL_IDS[ModelTier.BALANCED]

    def test_for_agent_ceo(self):
        assert ModelRouter.for_agent("ceo") == MODEL_IDS[ModelTier.FRONTIER]

    def test_for_agent_worker(self):
        assert ModelRouter.for_agent("worker") == MODEL_IDS[ModelTier.BALANCED]

    def test_for_agent_system(self):
        assert ModelRouter.for_agent("system") == MODEL_IDS[ModelTier.FAST]

    def test_for_agent_unknown_returns_balanced(self):
        assert ModelRouter.for_agent("nonexistent") == MODEL_IDS[ModelTier.BALANCED]


class TestCostEstimator:
    def test_zero_tokens_zero_cost(self):
        assert estimate_cost("claude-sonnet-4-6", 0, 0) == 0.0

    def test_unknown_model_zero_cost(self):
        assert estimate_cost("unknown-model", 1000, 500) == 0.0

    def test_cache_read_cheaper_than_input(self):
        full_cost = estimate_cost("claude-sonnet-4-6", 1_000_000, 0)
        cache_cost = estimate_cost("claude-sonnet-4-6", 0, 0, cache_read_tokens=1_000_000)
        assert cache_cost < full_cost

    def test_estimate_from_usage_dict(self):
        usage = {"input": 1000, "output": 200, "cache_read": 500, "cache_write": 0}
        cost = estimate_from_usage("claude-sonnet-4-6", usage)
        assert cost > 0

    def test_opus_more_expensive_than_haiku(self):
        cost_opus = estimate_cost("claude-opus-4-7", 10_000, 2_000)
        cost_haiku = estimate_cost("claude-haiku-4-5-20251001", 10_000, 2_000)
        assert cost_opus > cost_haiku
