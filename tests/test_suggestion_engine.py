"""Tests for sovereign/proactive/suggestion_engine.py — all 6 default rules."""
from __future__ import annotations

import time
from datetime import date, timedelta

import pytest

from sovereign.proactive.suggestion_engine import Suggestion, SuggestionEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> SuggestionEngine:
    return SuggestionEngine()


def _today() -> str:
    return date.today().isoformat()


def _days(delta: int) -> str:
    return (date.today() + timedelta(days=delta)).isoformat()


# ---------------------------------------------------------------------------
# Suggestion dataclass
# ---------------------------------------------------------------------------

class TestSuggestion:
    def test_not_expired_by_default(self):
        s = Suggestion("id", "T", "D", "A")
        assert not s.expired

    def test_expired_when_past(self):
        s = Suggestion("id", "T", "D", "A", expires_at=time.time() - 1)
        assert s.expired

    def test_not_expired_when_future(self):
        s = Suggestion("id", "T", "D", "A", expires_at=time.time() + 3600)
        assert not s.expired


# ---------------------------------------------------------------------------
# SuggestionEngine core
# ---------------------------------------------------------------------------

class TestSuggestionEngineCore:
    def test_evaluate_returns_list(self):
        engine = _engine()
        result = engine.evaluate({})
        assert isinstance(result, list)

    def test_sorted_by_priority_descending(self):
        engine = _engine()
        snap = {
            "financial": [{"monthly_cashflow": 100}],   # priority 0.9
        }
        results = engine.evaluate(snap)
        priorities = [s.priority for s in results]
        assert priorities == sorted(priorities, reverse=True)

    def test_dismissed_suggestion_excluded(self):
        engine = _engine()
        snap = {"financial": [{"monthly_cashflow": 100}]}
        engine.evaluate(snap)
        engine.dismiss("low_cashflow")
        results = engine.evaluate(snap)
        assert all(s.suggestion_id != "low_cashflow" for s in results)

    def test_top_returns_at_most_n(self):
        engine = _engine()
        engine.evaluate({})
        assert len(engine.top(3)) <= 3

    def test_custom_rule_registered_and_called(self):
        engine = _engine()
        called = []

        def my_rule(snap):
            called.append(snap)
            return [Suggestion("custom", "Custom", "Desc", "action", priority=0.99)]

        engine.register_rule("my_rule", my_rule)
        results = engine.evaluate({"key": "val"})
        assert called
        ids = [s.suggestion_id for s in results]
        assert "custom" in ids

    def test_failing_rule_does_not_crash_engine(self):
        engine = _engine()

        def bad_rule(snap):
            raise RuntimeError("oops")

        engine.register_rule("bad", bad_rule)
        results = engine.evaluate({})  # should not raise
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# low_cashflow_rule
# ---------------------------------------------------------------------------

class TestLowCashflowRule:
    def test_triggers_when_cashflow_below_500(self):
        engine = _engine()
        snap = {"financial": [{"monthly_cashflow": 200}]}
        results = engine.evaluate(snap)
        ids = [s.suggestion_id for s in results]
        assert "low_cashflow" in ids

    def test_no_trigger_when_cashflow_above_threshold(self):
        engine = _engine()
        snap = {"financial": [{"monthly_cashflow": 2000}]}
        results = engine.evaluate(snap)
        assert all(s.suggestion_id != "low_cashflow" for s in results)

    def test_works_with_dict_format(self):
        engine = _engine()
        snap = {"financial": {"monthly_cashflow": 100}}
        results = engine.evaluate(snap)
        ids = [s.suggestion_id for s in results]
        assert "low_cashflow" in ids

    def test_no_trigger_when_financial_missing(self):
        engine = _engine()
        results = engine.evaluate({})
        assert all(s.suggestion_id != "low_cashflow" for s in results)


# ---------------------------------------------------------------------------
# overdue_actions_rule
# ---------------------------------------------------------------------------

class TestOverdueActionsRule:
    def test_triggers_for_overdue_action(self):
        engine = _engine()
        snap = {"next_action": [
            {"title": "Do X", "due_date": _days(-1), "done": False}
        ]}
        results = engine.evaluate(snap)
        assert any(s.suggestion_id == "overdue_actions" for s in results)

    def test_no_trigger_for_future_action(self):
        engine = _engine()
        snap = {"next_action": [
            {"title": "Do Y", "due_date": _days(3), "done": False}
        ]}
        results = engine.evaluate(snap)
        assert all(s.suggestion_id != "overdue_actions" for s in results)

    def test_no_trigger_for_completed_action(self):
        engine = _engine()
        snap = {"next_action": [
            {"title": "Done", "due_date": _days(-1), "done": True}
        ]}
        results = engine.evaluate(snap)
        assert all(s.suggestion_id != "overdue_actions" for s in results)

    def test_description_includes_titles(self):
        engine = _engine()
        snap = {"next_action": [
            {"title": "Fix bug", "due_date": _days(-2), "done": False}
        ]}
        results = engine.evaluate(snap)
        match = next(s for s in results if s.suggestion_id == "overdue_actions")
        assert "Fix bug" in match.description


# ---------------------------------------------------------------------------
# project_deadline_rule
# ---------------------------------------------------------------------------

class TestProjectDeadlineRule:
    def test_triggers_for_deadline_within_14_days(self):
        engine = _engine()
        snap = {"projects": [
            {"name": "Alpha", "deadline": _days(7), "status": "active", "progress": 40}
        ]}
        results = engine.evaluate(snap)
        ids = [s.suggestion_id for s in results]
        assert any("deadline_" in i for i in ids)

    def test_no_trigger_for_deadline_beyond_14_days(self):
        engine = _engine()
        snap = {"projects": [
            {"name": "Beta", "deadline": _days(30), "status": "active"}
        ]}
        results = engine.evaluate(snap)
        assert all("deadline_" not in s.suggestion_id for s in results)

    def test_no_trigger_for_completed_project(self):
        engine = _engine()
        snap = {"projects": [
            {"name": "Done", "deadline": _days(2), "status": "completed"}
        ]}
        results = engine.evaluate(snap)
        assert all("deadline_" not in s.suggestion_id for s in results)


# ---------------------------------------------------------------------------
# open_decisions_rule
# ---------------------------------------------------------------------------

class TestOpenDecisionsRule:
    def test_triggers_when_two_or_more_open(self):
        engine = _engine()
        snap = {"decision": [
            {"title": "D1", "status": "open"},
            {"title": "D2", "status": "open"},
        ]}
        results = engine.evaluate(snap)
        assert any(s.suggestion_id == "open_decisions" for s in results)

    def test_no_trigger_for_single_open_decision(self):
        engine = _engine()
        snap = {"decision": [{"title": "D1", "status": "open"}]}
        results = engine.evaluate(snap)
        assert all(s.suggestion_id != "open_decisions" for s in results)

    def test_no_trigger_when_all_decided(self):
        engine = _engine()
        snap = {"decision": [
            {"title": "D1", "status": "decided"},
            {"title": "D2", "status": "decided"},
        ]}
        results = engine.evaluate(snap)
        assert all(s.suggestion_id != "open_decisions" for s in results)


# ---------------------------------------------------------------------------
# budget_overspend_rule
# ---------------------------------------------------------------------------

class TestBudgetOverspendRule:
    def test_triggers_when_above_90_pct(self):
        engine = _engine()
        snap = {"financial": [{"monthly_budget": 1000, "monthly_spent": 950}]}
        results = engine.evaluate(snap)
        assert any(s.suggestion_id == "budget_overspend" for s in results)

    def test_no_trigger_when_below_90_pct(self):
        engine = _engine()
        snap = {"financial": [{"monthly_budget": 1000, "monthly_spent": 800}]}
        results = engine.evaluate(snap)
        assert all(s.suggestion_id != "budget_overspend" for s in results)

    def test_metadata_contains_pct(self):
        engine = _engine()
        snap = {"financial": [{"monthly_budget": 1000, "monthly_spent": 950}]}
        results = engine.evaluate(snap)
        match = next(s for s in results if s.suggestion_id == "budget_overspend")
        assert match.metadata["pct"] == 95


# ---------------------------------------------------------------------------
# stale_memory_rule
# ---------------------------------------------------------------------------

class TestStaleMemoryRule:
    def test_triggers_for_empty_domain(self):
        engine = _engine()
        snap = {"custom_domain": {}}
        results = engine.evaluate(snap)
        assert any(s.suggestion_id == "empty_custom_domain_memory" for s in results)

    def test_no_trigger_for_populated_domain(self):
        engine = _engine()
        snap = {"custom_domain": {"key": "value"}}
        results = engine.evaluate(snap)
        assert all(s.suggestion_id != "empty_custom_domain_memory" for s in results)

    def test_conversation_history_ignored(self):
        engine = _engine()
        snap = {"conversation_history": {}}
        results = engine.evaluate(snap)
        assert all("conversation_history" not in s.suggestion_id for s in results)
