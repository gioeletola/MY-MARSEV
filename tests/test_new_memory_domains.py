"""Tests for new memory domains: NextActionStore, PersonalVersionStore,
PersonalConstitutionStore, BusinessIdeaMemoryStore."""
from __future__ import annotations

import pathlib


from sovereign.memory.domains.business_idea import BusinessIdea, BusinessIdeaMemoryStore
from sovereign.memory.domains.next_action import NextAction, NextActionStore
from sovereign.memory.domains.personal_constitution import (
    PersonalConstitution,
    PersonalConstitutionStore,
    RedFlag,
)
from sovereign.memory.domains.personal_version import PersonalVersion, PersonalVersionStore


# ---------------------------------------------------------------------------
# NextActionStore
# ---------------------------------------------------------------------------


class TestNextActionStore:
    def test_add_and_pending(self, tmp_path: pathlib.Path):
        store = NextActionStore(tmp_path / "next_action.json")
        store.add_action(NextAction(action_id="a1", title="Buy groceries"))
        store.add_action(NextAction(action_id="a2", title="Call dentist"))

        pending = store.pending()
        ids = {a.action_id for a in pending}
        assert "a1" in ids
        assert "a2" in ids

    def test_urgent(self, tmp_path: pathlib.Path):
        store = NextActionStore(tmp_path / "next_action.json")
        store.add_action(NextAction(action_id="u1", title="Critical task", priority="critical"))
        store.add_action(NextAction(action_id="u2", title="Low task", priority="low"))

        urgent = store.urgent()
        ids = {a.action_id for a in urgent}
        assert "u1" in ids
        assert "u2" not in ids

    def test_overdue(self, tmp_path: pathlib.Path):
        store = NextActionStore(tmp_path / "next_action.json")
        store.add_action(NextAction(action_id="o1", title="Overdue task", due_date="2020-01-01"))
        store.add_action(NextAction(action_id="o2", title="Future task", due_date="2099-12-31"))

        overdue = store.overdue()
        ids = {a.action_id for a in overdue}
        assert "o1" in ids
        assert "o2" not in ids

    def test_complete_action(self, tmp_path: pathlib.Path):
        store = NextActionStore(tmp_path / "next_action.json")
        store.add_action(NextAction(action_id="c1", title="Complete me"))

        pending_before = {a.action_id for a in store.pending()}
        assert "c1" in pending_before

        store.complete_action("c1")

        pending_after = {a.action_id for a in store.pending()}
        assert "c1" not in pending_after

    def test_to_context_string(self, tmp_path: pathlib.Path):
        store = NextActionStore(tmp_path / "next_action.json")
        store.add_action(NextAction(action_id="ctx1", title="Context action"))

        result = store.to_context_string()
        assert "Next actions" in result


# ---------------------------------------------------------------------------
# PersonalVersionStore
# ---------------------------------------------------------------------------


class TestPersonalVersionStore:
    def test_save_and_latest(self, tmp_path: pathlib.Path):
        store = PersonalVersionStore(tmp_path / "personal_version.json")
        store.save_version(PersonalVersion(version_id="v1", period="2026-04"))

        latest = store.latest()
        assert latest is not None
        assert latest.period == "2026-04"

    def test_history(self, tmp_path: pathlib.Path):
        store = PersonalVersionStore(tmp_path / "personal_version.json")
        store.save_version(PersonalVersion(version_id="v1", period="2026-01"))
        store.save_version(PersonalVersion(version_id="v2", period="2026-02"))
        store.save_version(PersonalVersion(version_id="v3", period="2026-03"))

        history = store.history()
        assert len(history) == 3
        assert history[0].period == "2026-03"
        assert history[1].period == "2026-02"
        assert history[2].period == "2026-01"

    def test_trend_net_worth(self, tmp_path: pathlib.Path):
        store = PersonalVersionStore(tmp_path / "personal_version.json")
        store.save_version(PersonalVersion(version_id="v1", period="2026-01", net_worth=10000.0))
        store.save_version(PersonalVersion(version_id="v2", period="2026-02", net_worth=12000.0))

        trend = store.trend_net_worth()
        assert isinstance(trend, list)
        assert len(trend) == 2
        net_worths = [entry["net_worth"] for entry in trend]
        assert 10000.0 in net_worths
        assert 12000.0 in net_worths


# ---------------------------------------------------------------------------
# PersonalConstitutionStore
# ---------------------------------------------------------------------------


class TestPersonalConstitutionStore:
    def test_get_empty(self, tmp_path: pathlib.Path):
        store = PersonalConstitutionStore(tmp_path / "personal_constitution.json")
        constitution = store.get_constitution()
        assert isinstance(constitution, PersonalConstitution)

    def test_update_constitution(self, tmp_path: pathlib.Path):
        store = PersonalConstitutionStore(tmp_path / "personal_constitution.json")
        store.update_constitution(core_values=["freedom", "mastery"])

        constitution = store.get_constitution()
        assert "freedom" in constitution.core_values
        assert "mastery" in constitution.core_values

    def test_add_red_flag(self, tmp_path: pathlib.Path):
        store = PersonalConstitutionStore(tmp_path / "personal_constitution.json")
        flag = RedFlag(flag_id="rf1", title="Spending spiral", severity="critical")
        store.add_red_flag(flag)

        critical_flags = store.red_flags_by_severity("critical")
        ids = {f.flag_id for f in critical_flags}
        assert "rf1" in ids


# ---------------------------------------------------------------------------
# BusinessIdeaMemoryStore
# ---------------------------------------------------------------------------


class TestBusinessIdeaMemoryStore:
    def test_add_and_by_status(self, tmp_path: pathlib.Path):
        store = BusinessIdeaMemoryStore(tmp_path / "business_idea.json")
        store.add_idea(BusinessIdea(idea_id="bi1", name="SaaS Tool", status="idea"))

        ideas = store.by_status("idea")
        ids = {i.idea_id for i in ideas}
        assert "bi1" in ids

    def test_top_scored(self, tmp_path: pathlib.Path):
        store = BusinessIdeaMemoryStore(tmp_path / "business_idea.json")
        store.add_idea(BusinessIdea(idea_id="ts1", name="Idea A", score=5))
        store.add_idea(BusinessIdea(idea_id="ts2", name="Idea B", score=8))
        store.add_idea(BusinessIdea(idea_id="ts3", name="Idea C", score=3))

        top = store.top_scored(2)
        assert len(top) == 2
        assert top[0].score == 8
        assert top[1].score == 5

    def test_to_context_string(self, tmp_path: pathlib.Path):
        store = BusinessIdeaMemoryStore(tmp_path / "business_idea.json")
        store.add_idea(BusinessIdea(idea_id="ctx1", name="Context Idea"))

        result = store.to_context_string()
        assert "Business ideas" in result
