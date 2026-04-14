"""
Routing rules loaded from config/models.yaml.

Provides a YAML-driven alternative to the hardcoded ModelRouter logic,
allowing operators to tune routing without changing code.
"""
from __future__ import annotations

import pathlib
from typing import Any

import yaml


def load_routing_rules(config_path: str = "config/models.yaml") -> list[dict[str, Any]]:
    """Load routing rules from the models.yaml config file."""
    path = pathlib.Path(config_path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("routing_rules", [])


def apply_rules(
    rules: list[dict[str, Any]],
    context: dict[str, Any],
    default: str = "balanced",
) -> str:
    """
    Evaluate routing rules in order and return the first matching tier name.

    Context keys: complexity_above, is_sensitive, latency_budget_ms_below, etc.
    """
    for rule in rules:
        condition = rule.get("if", {})
        if _matches(condition, context):
            return rule.get("use", default)
    return rule.get("default", default) if rules else default  # type: ignore[return-value]


def _matches(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    for key, value in condition.items():
        ctx_val = context.get(key)
        if ctx_val is None:
            return False
        if key.endswith("_above") and not (ctx_val > value):
            return False
        if key.endswith("_below") and not (ctx_val < value):
            return False
        if not key.endswith(("_above", "_below")) and ctx_val != value:
            return False
    return True
