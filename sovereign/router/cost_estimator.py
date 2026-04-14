"""
Token cost estimator — rough price estimates for planning purposes.

Prices are approximations (USD per million tokens) as of 2025.
Always verify against the Anthropic pricing page before relying on these.
"""
from __future__ import annotations

# USD per 1M tokens (input / output)
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input":        15.00,
        "output":       75.00,
        "cache_write":   3.75,
        "cache_read":    1.50,
    },
    "claude-sonnet-4-6": {
        "input":         3.00,
        "output":       15.00,
        "cache_write":   0.375,
        "cache_read":    0.30,
    },
    "claude-haiku-4-5-20251001": {
        "input":         0.80,
        "output":        4.00,
        "cache_write":   0.10,
        "cache_read":    0.08,
    },
}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """
    Estimate the USD cost of a Claude API call.

    Returns cost in USD (float). Returns 0.0 for unknown models.
    """
    prices = PRICING.get(model, {})
    if not prices:
        return 0.0

    cost = (
        (input_tokens        / 1_000_000) * prices.get("input",        0.0)
        + (output_tokens     / 1_000_000) * prices.get("output",       0.0)
        + (cache_read_tokens / 1_000_000) * prices.get("cache_read",   0.0)
        + (cache_write_tokens/ 1_000_000) * prices.get("cache_write",  0.0)
    )
    return round(cost, 6)


def estimate_from_usage(model: str, usage: dict[str, int]) -> float:
    """Estimate cost from a token usage dict (as returned by ClaudeClient.get_usage)."""
    return estimate_cost(
        model=model,
        input_tokens=usage.get("input", 0),
        output_tokens=usage.get("output", 0),
        cache_read_tokens=usage.get("cache_read", 0),
        cache_write_tokens=usage.get("cache_write", 0),
    )
