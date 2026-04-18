"""
V2 tests: FinancialMemoryStore, ProjectMemoryStore, CSVImportTool, GoalMonitor,
SuggestionEngine, IntegrationManager — all with isolated tmp_path fixtures.
"""
from __future__ import annotations

import json
import pathlib
import time
import uuid
import pytest


# ---------------------------------------------------------------------------
# FinancialMemoryStore
# ---------------------------------------------------------------------------

class TestFinancialMemoryStore:
    def _store(self, tmp_path):
        from sovereign.memory.domains.financial import FinancialMemoryStore
        return FinancialMemoryStore(data_file=tmp_path / "financial.json")

    def test_empty_snapshot(self, tmp_path):
        store = self._store(tmp_path)
        snap = store.get_snapshot()
        assert isinstance(snap, dict)

    def test_set_and_get_snapshot(self, tmp_path):
        store = self._store(tmp_path)
        store.set_snapshot(monthly_income=10000.0, monthly_expenses=6000.0)
        snap = store.get_snapshot()
        assert snap["monthly_income"] == 10000.0
        assert snap["monthly_cashflow"] == 4000.0
        assert snap["savings_rate"] == pytest.approx(40.0)

    def test_set_holding_new(self, tmp_path):
        store = self._store(tmp_path)
        store.set_holding("BTC", "crypto", 50000.0, ticker="BTC")
        holdings = store.get_portfolio()
        assert len(holdings) == 1
        assert holdings[0]["name"] == "BTC"
        assert holdings[0]["value"] == 50000.0

    def test_set_holding_update(self, tmp_path):
        store = self._store(tmp_path)
        store.set_holding("ETH", "crypto", 3000.0)
        store.set_holding("ETH", "crypto", 4000.0)
        holdings = store.get_portfolio()
        assert len(holdings) == 1
        assert holdings[0]["value"] == 4000.0

    def test_portfolio_by_class(self, tmp_path):
        store = self._store(tmp_path)
        store.set_holding("BTC",  "crypto",    50000.0)
        store.set_holding("ETH",  "crypto",    20000.0)
        store.set_holding("AAPL", "equities",  15000.0)
        by_class = store.get_portfolio_by_class()
        assert by_class["crypto"]    == pytest.approx(70000.0)
        assert by_class["equities"]  == pytest.approx(15000.0)

    def test_add_transaction(self, tmp_path):
        store = self._store(tmp_path)
        tx = store.add_transaction("2026-04-01", "Salary", 5000.0, category="income")
        assert tx["tx_id"]
        assert tx["amount"] == 5000.0
        assert tx["category"] == "income"

    def test_get_transactions_filter_by_date(self, tmp_path):
        store = self._store(tmp_path)
        store.add_transaction("2026-01-15", "Old tx",  100.0)
        store.add_transaction("2026-04-10", "New tx", 200.0)
        txs = store.get_transactions(date_from="2026-03-01")
        assert len(txs) == 1
        assert txs[0]["description"] == "New tx"

    def test_get_transactions_filter_by_category(self, tmp_path):
        store = self._store(tmp_path)
        store.add_transaction("2026-04-01", "Groceries", -150.0, category="food")
        store.add_transaction("2026-04-02", "Netflix",   -15.0,  category="entertainment")
        txs = store.get_transactions(category="food")
        assert len(txs) == 1
        assert txs[0]["category"] == "food"

    def test_cashflow_by_month(self, tmp_path):
        store = self._store(tmp_path)
        store.add_transaction("2026-03-15", "Salary",    5000.0)
        store.add_transaction("2026-03-20", "Rent",     -1500.0)
        store.add_transaction("2026-04-01", "Salary",    5000.0)
        bars = store.get_cashflow_by_month(months=12)
        months = {b["month"]: b for b in bars}
        assert "2026-03" in months
        assert months["2026-03"]["income"]   == pytest.approx(5000.0)
        assert months["2026-03"]["expenses"] == pytest.approx(1500.0)
        assert months["2026-03"]["cashflow"] == pytest.approx(3500.0)

    def test_import_csv_basic(self, tmp_path):
        store = self._store(tmp_path)
        csv_text = "date,description,amount\n2026-04-01,Coffee,-4.50\n2026-04-02,Payroll,3000.00\n"
        result = store.import_csv_transactions(csv_text)
        assert result["imported"] == 2
        assert result["skipped"]  == 0
        assert len(result["errors"]) == 0
        txs = store.get_transactions(limit=10)
        assert len(txs) == 2

    def test_import_csv_euro_date_format(self, tmp_path):
        store = self._store(tmp_path)
        csv_text = "data,descrizione,importo\n01/04/2026,Caffè,-2.50\n02/04/2026,Stipendio,2000.00\n"
        result = store.import_csv_transactions(
            csv_text, date_col="data", desc_col="descrizione", amount_col="importo"
        )
        assert result["imported"] == 2

    def test_import_csv_skips_empty_rows(self, tmp_path):
        store = self._store(tmp_path)
        csv_text = "date,description,amount\n,,\n2026-04-01,Lunch,-12.00\n"
        result = store.import_csv_transactions(csv_text)
        assert result["imported"] == 1
        assert result["skipped"]  == 1

    def test_get_summary_shape(self, tmp_path):
        store = self._store(tmp_path)
        store.set_snapshot(monthly_income=8000.0, monthly_expenses=4000.0)
        store.set_holding("TSLA", "equities", 20000.0)
        store.add_transaction("2026-04-01", "Tx", 100.0)
        s = store.get_summary()
        for key in ("net_worth","monthly_income","monthly_expenses","monthly_cashflow",
                    "savings_rate","portfolio_total","portfolio_by_class","transaction_count","cashflow_12m"):
            assert key in s, f"Missing key: {key}"
        assert s["portfolio_total"] == pytest.approx(20000.0)
        assert s["transaction_count"] == 1

    def test_net_worth_computed_from_holdings(self, tmp_path):
        store = self._store(tmp_path)
        store.set_holding("A", "cash",     10000.0)
        store.set_holding("B", "equities", 25000.0)
        snap = store.get_snapshot()
        assert snap["net_worth"] == pytest.approx(35000.0)


# ---------------------------------------------------------------------------
# ProjectMemoryStore
# ---------------------------------------------------------------------------

class TestProjectMemoryStore:
    def _store(self, tmp_path):
        from sovereign.memory.domains.project import ProjectMemoryStore
        return ProjectMemoryStore(data_file=tmp_path / "projects.json")

    def test_create_project(self, tmp_path):
        store = self._store(tmp_path)
        p = store.create_project("Alpha", description="Test project", owner="alice")
        assert p["project_id"]
        assert p["name"] == "Alpha"
        assert p["progress"] == 0

    def test_get_project(self, tmp_path):
        store = self._store(tmp_path)
        p = store.create_project("Beta")
        fetched = store.get_project(p["project_id"])
        assert fetched is not None
        assert fetched["name"] == "Beta"

    def test_get_nonexistent_project(self, tmp_path):
        store = self._store(tmp_path)
        assert store.get_project("nope") is None

    def test_update_project(self, tmp_path):
        store = self._store(tmp_path)
        p = store.create_project("Gamma")
        ok = store.update_project(p["project_id"], status="review", owner="bob")
        assert ok is True
        updated = store.get_project(p["project_id"])
        assert updated["status"] == "review"
        assert updated["owner"]  == "bob"

    def test_delete_project(self, tmp_path):
        store = self._store(tmp_path)
        p = store.create_project("Delete Me")
        ok = store.delete_project(p["project_id"])
        assert ok is True
        assert store.get_project(p["project_id"]) is None

    def test_delete_nonexistent(self, tmp_path):
        store = self._store(tmp_path)
        assert store.delete_project("ghost") is False

    def test_get_projects_filter_by_status(self, tmp_path):
        store = self._store(tmp_path)
        store.create_project("P1", status="active")
        store.create_project("P2", status="done")
        store.create_project("P3", status="active")
        active = store.get_projects(status="active")
        assert len(active) == 2
        done = store.get_projects(status="done")
        assert len(done) == 1

    def test_add_task(self, tmp_path):
        store = self._store(tmp_path)
        p = store.create_project("TaskTest")
        t = store.add_task(p["project_id"], "Write tests", priority=3)
        assert t is not None
        assert t["task_id"]
        assert t["title"] == "Write tests"
        assert t["status"] == "todo"

    def test_add_task_to_nonexistent_project(self, tmp_path):
        store = self._store(tmp_path)
        t = store.add_task("ghost", "Orphan task")
        assert t is None

    def test_complete_task_updates_progress(self, tmp_path):
        store = self._store(tmp_path)
        p  = store.create_project("Progress")
        t1 = store.add_task(p["project_id"], "Task A")
        t2 = store.add_task(p["project_id"], "Task B")
        store.complete_task(p["project_id"], t1["task_id"])
        updated = store.get_project(p["project_id"])
        assert updated["progress"] == 50  # 1 of 2 done

    def test_complete_all_tasks_100_percent(self, tmp_path):
        store = self._store(tmp_path)
        p  = store.create_project("Full")
        t  = store.add_task(p["project_id"], "Only task")
        store.complete_task(p["project_id"], t["task_id"])
        assert store.get_project(p["project_id"])["progress"] == 100

    def test_update_task(self, tmp_path):
        store = self._store(tmp_path)
        p = store.create_project("TaskUpdate")
        t = store.add_task(p["project_id"], "Original")
        ok = store.update_task(p["project_id"], t["task_id"], title="Updated", assignee="carol")
        assert ok is True
        proj = store.get_project(p["project_id"])
        task = next(x for x in proj["tasks"] if x["task_id"] == t["task_id"])
        assert task["title"]    == "Updated"
        assert task["assignee"] == "carol"

    def test_get_summary(self, tmp_path):
        store = self._store(tmp_path)
        store.create_project("A", status="active")
        store.create_project("B", status="active")
        store.create_project("C", status="blocked")
        store.create_project("D", status="done")
        s = store.get_summary()
        assert s["total"]   == 4
        assert s["active"]  == 2
        assert s["blocked"] == 1
        assert s["done"]    == 1

    def test_persistence(self, tmp_path):
        path = tmp_path / "projects.json"
        from sovereign.memory.domains.project import ProjectMemoryStore
        s1 = ProjectMemoryStore(data_file=path)
        p  = s1.create_project("Persist Me")
        s2 = ProjectMemoryStore(data_file=path)
        assert s2.get_project(p["project_id"]) is not None


# ---------------------------------------------------------------------------
# CSVImportTool
# ---------------------------------------------------------------------------

class TestCSVImportTool:
    @pytest.mark.asyncio
    async def test_import_action(self, tmp_path, monkeypatch):
        from sovereign.memory.domains import financial as fin_mod
        monkeypatch.setattr(fin_mod, "_DATA_FILE", tmp_path / "financial.json")
        from sovereign.tools.builtin.csv_import_tool import CSVImportTool
        tool = CSVImportTool()
        csv = "date,description,amount\n2026-04-01,Test,-10.00\n"
        result = await tool.execute(action="import", csv_text=csv)
        assert result["error"] is None
        assert result["result"]["imported"] == 1

    @pytest.mark.asyncio
    async def test_preview_action(self, tmp_path, monkeypatch):
        from sovereign.memory.domains import financial as fin_mod
        monkeypatch.setattr(fin_mod, "_DATA_FILE", tmp_path / "financial.json")
        from sovereign.tools.builtin.csv_import_tool import CSVImportTool
        tool = CSVImportTool()
        csv = "date,description,amount\n2026-04-01,A,-1.00\n2026-04-02,B,-2.00\n"
        result = await tool.execute(action="preview", csv_text=csv)
        assert result["error"] is None
        assert "headers" in result["result"]
        assert len(result["result"]["preview_rows"]) == 2

    @pytest.mark.asyncio
    async def test_missing_csv_returns_error(self):
        from sovereign.tools.builtin.csv_import_tool import CSVImportTool
        tool = CSVImportTool()
        result = await tool.execute(action="import")
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_file_import(self, tmp_path, monkeypatch):
        from sovereign.memory.domains import financial as fin_mod
        monkeypatch.setattr(fin_mod, "_DATA_FILE", tmp_path / "financial.json")
        csv_file = tmp_path / "bank.csv"
        csv_file.write_text("date,description,amount\n2026-04-05,Payroll,3000.00\n")
        from sovereign.tools.builtin.csv_import_tool import CSVImportTool
        tool = CSVImportTool()
        result = await tool.execute(action="import", filepath=str(csv_file))
        assert result["error"] is None
        assert result["result"]["imported"] == 1


# ---------------------------------------------------------------------------
# GoalMonitor
# ---------------------------------------------------------------------------

class TestGoalMonitor:
    def _monitor(self, tmp_path, monkeypatch):
        from sovereign.proactive import goal_monitor as mod
        monkeypatch.setattr(mod, "_DATA_FILE", tmp_path / "goals.json")
        from sovereign.proactive.goal_monitor import GoalMonitor
        return GoalMonitor()

    def test_add_and_list_goals(self, tmp_path, monkeypatch):
        from sovereign.proactive.goal_monitor import Goal
        gm = self._monitor(tmp_path, monkeypatch)
        g = Goal(goal_id="g1", title="Run 5K", description="Run 5K in under 30min",
                 target_value=5.0, unit="km")
        gm.add(g)
        assert len(gm.active_goals()) == 1

    def test_update_progress(self, tmp_path, monkeypatch):
        from sovereign.proactive.goal_monitor import Goal
        gm = self._monitor(tmp_path, monkeypatch)
        g = Goal(goal_id="g2", title="Save 10K", description="", target_value=10000.0)
        gm.add(g)
        updated = gm.update_progress("g2", 3000.0)
        assert updated is not None
        assert updated.progress_pct == pytest.approx(30.0)

    def test_goal_completed_when_target_reached(self, tmp_path, monkeypatch):
        from sovereign.proactive.goal_monitor import Goal, GoalStatus
        gm = self._monitor(tmp_path, monkeypatch)
        g = Goal(goal_id="g3", title="Hit 100%", description="", target_value=100.0)
        gm.add(g)
        gm.update_progress("g3", 100.0)
        goal = gm.active_goals()
        assert not any(x.goal_id == "g3" for x in goal)

    def test_overdue_detection(self, tmp_path, monkeypatch):
        from sovereign.proactive.goal_monitor import Goal
        gm = self._monitor(tmp_path, monkeypatch)
        past_deadline = time.time() - 3600
        g = Goal(goal_id="g4", title="Overdue Goal", description="", target_value=100.0,
                 deadline=past_deadline)
        gm.add(g)
        assert gm.overdue_goals()[0].goal_id == "g4"

    def test_summary_counts(self, tmp_path, monkeypatch):
        from sovereign.proactive.goal_monitor import Goal
        gm = self._monitor(tmp_path, monkeypatch)
        gm.add(Goal(goal_id="a", title="A", description="", target_value=10.0))
        gm.add(Goal(goal_id="b", title="B", description="", target_value=10.0))
        gm.complete("a")
        s = gm.summary()
        assert s["total"] == 2
        assert s["completed"] == 1
        assert s["active"] == 1


# ---------------------------------------------------------------------------
# SuggestionEngine
# ---------------------------------------------------------------------------

class TestSuggestionEngine:
    def test_low_cashflow_triggers_suggestion(self):
        from sovereign.proactive.suggestion_engine import SuggestionEngine
        engine = SuggestionEngine()
        snap = {"financial": {"monthly_cashflow": 100}}
        suggestions = engine.evaluate(snap)
        ids = [s.suggestion_id for s in suggestions]
        assert "low_cashflow" in ids

    def test_no_suggestion_when_cashflow_healthy(self):
        from sovereign.proactive.suggestion_engine import SuggestionEngine
        engine = SuggestionEngine()
        snap = {"financial": {"monthly_cashflow": 5000}}
        suggestions = engine.evaluate(snap)
        ids = [s.suggestion_id for s in suggestions]
        assert "low_cashflow" not in ids

    def test_dismiss_suppresses_suggestion(self):
        from sovereign.proactive.suggestion_engine import SuggestionEngine
        engine = SuggestionEngine()
        snap = {"financial": {"monthly_cashflow": 100}}
        suggestions = engine.evaluate(snap)
        assert any(s.suggestion_id == "low_cashflow" for s in suggestions)
        engine.dismiss("low_cashflow")
        suggestions2 = engine.evaluate(snap)
        assert not any(s.suggestion_id == "low_cashflow" for s in suggestions2)

    def test_custom_rule_registration(self):
        from sovereign.proactive.suggestion_engine import SuggestionEngine, Suggestion
        engine = SuggestionEngine()
        def my_rule(snap):
            return [Suggestion(suggestion_id="test_rule", title="Test", description="",
                               action="noop", priority=1.0)]
        engine.register_rule("my_rule", my_rule)
        sug = engine.evaluate({})
        assert any(s.suggestion_id == "test_rule" for s in sug)


# ---------------------------------------------------------------------------
# IntegrationManager
# ---------------------------------------------------------------------------

class TestIntegrationManager:
    def _manager(self, tmp_path, monkeypatch):
        from sovereign.integrations import integration_manager as mod
        monkeypatch.setattr(mod, "_CONFIG_PATH", tmp_path / "integrations.json")
        from sovereign.integrations.integration_manager import IntegrationManager
        return IntegrationManager()

    def test_list_all_includes_known_integrations(self, tmp_path, monkeypatch):
        mgr = self._manager(tmp_path, monkeypatch)
        ids = {i["id"] for i in mgr.list_all()}
        assert "email" in ids
        assert "calendar" in ids
        assert "crm" in ids

    def test_connect_email(self, tmp_path, monkeypatch):
        from sovereign.integrations import email_integration as em
        monkeypatch.setattr(em, "_OUTBOX_FILE", tmp_path / "outbox.json")
        monkeypatch.setattr(em, "_INBOX_FILE",  tmp_path / "inbox.json")
        mgr = self._manager(tmp_path, monkeypatch)
        from sovereign.integrations.base_integration import IntegrationConfig
        cfg = IntegrationConfig(integration_id="email", name="email", enabled=True, credentials={})
        ok = mgr.connect("email", cfg)
        assert ok is True

    def test_connect_unknown_integration(self, tmp_path, monkeypatch):
        mgr = self._manager(tmp_path, monkeypatch)
        from sovereign.integrations.base_integration import IntegrationConfig
        cfg = IntegrationConfig(integration_id="ghost", name="ghost", enabled=True, credentials={})
        ok = mgr.connect("ghost", cfg)
        assert ok is False

    def test_health_returns_all_statuses(self, tmp_path, monkeypatch):
        mgr = self._manager(tmp_path, monkeypatch)
        h = mgr.health()
        assert isinstance(h, dict)
        assert "email" in h

    def test_config_persisted_after_connect(self, tmp_path, monkeypatch):
        from sovereign.integrations import email_integration as em
        monkeypatch.setattr(em, "_OUTBOX_FILE", tmp_path / "outbox.json")
        monkeypatch.setattr(em, "_INBOX_FILE",  tmp_path / "inbox.json")
        from sovereign.integrations import integration_manager as mod
        monkeypatch.setattr(mod, "_CONFIG_PATH", tmp_path / "integrations.json")
        from sovereign.integrations.integration_manager import IntegrationManager
        from sovereign.integrations.base_integration import IntegrationConfig
        mgr = IntegrationManager()
        cfg = IntegrationConfig(integration_id="email", name="email", enabled=True, credentials={})
        mgr.connect("email", cfg)
        assert (tmp_path / "integrations.json").exists()
        data = json.loads((tmp_path / "integrations.json").read_text())
        assert "email" in data
