"""Tests for sovereign/intelligence/model_catalog.py."""
from __future__ import annotations

import pytest

from sovereign.intelligence.model_catalog import (
    ModelCatalog, ModelTier, ProviderType, get_model_catalog,
)


@pytest.fixture
def catalog() -> ModelCatalog:
    return ModelCatalog()


def test_catalog_has_entries(catalog):
    assert len(catalog.all()) > 0


def test_catalog_get_known_model(catalog):
    entry = catalog.get("claude-sonnet-4-6")
    assert entry is not None
    assert entry.provider == "anthropic"
    assert entry.tier == ModelTier.BALANCED


def test_catalog_get_missing(catalog):
    assert catalog.get("nonexistent-model-xyz") is None


def test_catalog_by_provider_anthropic(catalog):
    models = catalog.by_provider("anthropic")
    assert len(models) >= 3
    for m in models:
        assert m.provider == "anthropic"


def test_catalog_by_tier_frontier(catalog):
    models = catalog.by_tier(ModelTier.FRONTIER)
    assert len(models) > 0
    for m in models:
        assert m.tier == ModelTier.FRONTIER


def test_catalog_local_models(catalog):
    local = catalog.local_models()
    assert len(local) > 0
    for m in local:
        assert m.offline_capable is True


def test_catalog_privacy_safe(catalog):
    private = catalog.privacy_safe_models()
    assert len(private) > 0
    for m in private:
        assert m.privacy_safe is True


def test_catalog_for_use_case_default(catalog):
    default_models = catalog.for_use_case("default")
    assert len(default_models) >= 1
    ids = {m.model_id for m in default_models}
    assert "claude-sonnet-4-6" in ids


def test_catalog_cheapest_sorts_ascending(catalog):
    cheapest = catalog.cheapest()
    # Local (free) models should be first
    assert cheapest[0].cost_per_1k_input_usd == 0.0
    # Costs are non-decreasing
    for i in range(len(cheapest) - 1):
        assert cheapest[i].cost_per_1k_input_usd <= cheapest[i + 1].cost_per_1k_input_usd


def test_catalog_cheapest_with_max_cost(catalog):
    very_cheap = catalog.cheapest(max_input_cost=0.001)
    for m in very_cheap:
        assert m.cost_per_1k_input_usd <= 0.001


def test_catalog_to_dict_list(catalog):
    dicts = catalog.to_dict_list()
    assert len(dicts) > 0
    required_keys = {
        "model_id", "provider", "display_name", "provider_type", "tier",
        "privacy_safe", "cost_per_1k_input_usd", "offline_capable",
    }
    for d in dicts:
        for key in required_keys:
            assert key in d, f"Missing key: {key}"


def test_catalog_singleton():
    c1 = get_model_catalog()
    c2 = get_model_catalog()
    assert c1 is c2


def test_model_entry_capability_scores(catalog):
    opus = catalog.get("claude-opus-4-6")
    assert opus is not None
    assert opus.reasoning_strength >= 0.9
    assert opus.coding_strength >= 0.9
    assert opus.context_window_tokens == 200_000


def test_qwen_models_are_private(catalog):
    qwen_models = catalog.by_provider("qwen")
    assert len(qwen_models) > 0
    for m in qwen_models:
        assert m.privacy_safe is True
        assert m.offline_capable is True
        assert m.cost_per_1k_input_usd == 0.0


def test_provider_type_enum():
    assert ProviderType.CLOUD == "cloud"
    assert ProviderType.LOCAL == "local"
    assert ProviderType.OPENAI_COMPAT == "openai_compat"


def test_model_tier_enum():
    assert ModelTier.FRONTIER == "frontier"
    assert ModelTier.BALANCED == "balanced"
    assert ModelTier.FAST == "fast"
    assert ModelTier.LOCAL == "local"
