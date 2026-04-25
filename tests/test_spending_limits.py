from __future__ import annotations

import pathlib

from sovereign.governance.spending_limits import (
    SpendingCategory,
    SpendingLimit,
    SpendingLimitsEngine,
)


def _engine(tmp_path: pathlib.Path) -> SpendingLimitsEngine:
    return SpendingLimitsEngine(persist_path=tmp_path / "spending.jsonl")


def test_check_allows_under_limit(tmp_path: pathlib.Path):
    engine = _engine(tmp_path)
    allowed, reason = engine.check(SpendingCategory.TOKENS, 0.001)
    assert allowed is True
    assert reason == ""


def test_check_blocks_over_per_action(tmp_path: pathlib.Path):
    engine = _engine(tmp_path)
    engine.set_limit(
        SpendingLimit(
            category=SpendingCategory.TOKENS,
            daily_limit=1000.0,
            monthly_limit=10000.0,
            per_action_limit=0.001,
        )
    )
    allowed, reason = engine.check(SpendingCategory.TOKENS, 0.01)
    assert allowed is False
    assert isinstance(reason, str)
    assert len(reason) > 0


def test_record_and_daily_usage(tmp_path: pathlib.Path):
    engine = _engine(tmp_path)
    engine.record_spend(SpendingCategory.TOKENS, 0.5, "first")
    engine.record_spend(SpendingCategory.TOKENS, 0.3, "second")
    assert abs(engine.daily_usage(SpendingCategory.TOKENS) - 0.8) < 1e-9


def test_summary_contains_categories(tmp_path: pathlib.Path):
    engine = _engine(tmp_path)
    summary = engine.summary()
    assert isinstance(summary, dict)
    assert "tokens" in summary
    assert "external_api" in summary


def test_blocks_over_daily_limit(tmp_path: pathlib.Path):
    engine = _engine(tmp_path)
    engine.set_limit(
        SpendingLimit(
            category=SpendingCategory.TOKENS,
            daily_limit=0.001,
            monthly_limit=10000.0,
            per_action_limit=10.0,
        )
    )
    engine.record_spend(SpendingCategory.TOKENS, 0.001, "hit the cap")
    allowed, reason = engine.check(SpendingCategory.TOKENS, 0.001)
    assert allowed is False
    assert "daily" in reason.lower()
