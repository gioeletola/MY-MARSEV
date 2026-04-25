from __future__ import annotations

import time
import pathlib

import sovereign.proactive.goal_monitor as gm_mod
from sovereign.proactive.goal_monitor import Goal, GoalMonitor, GoalStatus


def _make_goal(goal_id: str, target: float = 100.0, **kwargs) -> Goal:
    return Goal(
        goal_id=goal_id,
        title=f"Goal {goal_id}",
        description="test",
        target_value=target,
        **kwargs,
    )


def test_add_and_active(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setattr(gm_mod, "_DATA_FILE", tmp_path / "goals.json")
    monitor = GoalMonitor()
    monitor.add(_make_goal("g1"))
    monitor.add(_make_goal("g2"))
    assert len(monitor.active_goals()) == 2


def test_update_progress(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setattr(gm_mod, "_DATA_FILE", tmp_path / "goals.json")
    monitor = GoalMonitor()
    monitor.add(_make_goal("g1", target=100.0))
    updated = monitor.update_progress("g1", 80.0)
    assert updated is not None
    assert updated.progress_pct == 80.0


def test_complete_on_target(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setattr(gm_mod, "_DATA_FILE", tmp_path / "goals.json")
    monitor = GoalMonitor()
    monitor.add(_make_goal("g1", target=50.0))
    updated = monitor.update_progress("g1", 50.0)
    assert updated.status == GoalStatus.COMPLETED


def test_complete(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setattr(gm_mod, "_DATA_FILE", tmp_path / "goals.json")
    monitor = GoalMonitor()
    monitor.add(_make_goal("g1"))
    monitor.complete("g1")
    assert all(g.goal_id != "g1" for g in monitor.active_goals())


def test_overdue(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setattr(gm_mod, "_DATA_FILE", tmp_path / "goals.json")
    monitor = GoalMonitor()
    monitor.add(_make_goal("g1", deadline=time.time() - 1))
    assert any(g.goal_id == "g1" for g in monitor.overdue_goals())


def test_at_risk(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setattr(gm_mod, "_DATA_FILE", tmp_path / "goals.json")
    monitor = GoalMonitor()
    monitor.add(_make_goal("g1", target=100.0, current_value=10.0, deadline=time.time() + 3600))
    at_risk = monitor.at_risk_goals(pct_threshold=25.0)
    assert any(g.goal_id == "g1" for g in at_risk)


def test_summary_counts(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setattr(gm_mod, "_DATA_FILE", tmp_path / "goals.json")
    monitor = GoalMonitor()
    monitor.add(_make_goal("g1"))
    monitor.add(_make_goal("g2"))
    monitor.add(_make_goal("g3"))
    monitor.complete("g3")
    summary = monitor.summary()
    assert summary["active"] == 2
    assert summary["completed"] == 1
    assert summary["total"] == 3
