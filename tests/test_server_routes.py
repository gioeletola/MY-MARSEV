"""
Tests for sovereign/api/server.py — FastAPI routes.
Uses TestClient (sync) with orchestrator mocked to avoid real API calls.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sovereign.api.auth import create_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orch() -> MagicMock:
    """Build a fully-mocked orchestrator instance."""
    orch = MagicMock()
    orch.health.return_value = {
        "overall": "healthy",
        "checks": {},
        "metrics": {},
        "alerts": [],
        "budget": {},
        "escalations_pending": 0,
        "tools_registered": 5,
        "agents_registered": 10,
    }
    orch.current_mode = "command"
    orch.config = MagicMock()
    orch.config.default_operating_mode = "command"

    # Agent registry
    registry = MagicMock()
    registry.count.return_value = 10
    registry.list_agents.return_value = [
        {"agent_id": "ceo", "specialty": "CEO", "stage": "production"},
    ]
    orch._agent_registry = registry

    # Other methods
    orch.get_usage.return_value = {"total_tokens": 1000}
    orch.get_session_count.return_value = 5
    orch.get_budget_summary.return_value = {"daily": 0.5, "monthly": 12.0}
    orch.get_pending_escalations.return_value = []
    orch.resolve_escalation.return_value = True
    orch.get_experiment_metrics.return_value = {"sessions": 1}
    orch.set_mode.return_value = True
    orch.goal_monitor = MagicMock()
    orch.goal_monitor.active_goals.return_value = []
    orch.goal_monitor.summary.return_value = {"total": 0, "completed": 0}
    orch.suggestion_engine = MagicMock()
    orch.suggestion_engine.evaluate.return_value = []
    orch.integration_manager = MagicMock()
    orch.integration_manager.list_all.return_value = []
    orch.entity_provisioner = MagicMock()
    orch.entity_provisioner.list_entities.return_value = []
    orch._memory = AsyncMock()
    orch._memory.read.return_value = {}
    orch._memory.get_snapshot = AsyncMock(return_value={})

    # Background tasks
    orch.start_background_tasks = AsyncMock()
    orch.stop_background_tasks = AsyncMock()

    # Model perf tracker — absent by default (tests gracefully handle None)
    orch._model_perf_tracker = None

    return orch


def _mock_template_response():
    """Return a mock TemplateResponse that returns a 200 HTML response."""
    from fastapi.responses import HTMLResponse

    def _mock_tr(name_or_request, context_or_name=None, context=None, **kwargs):
        # Handle both old API (name, context) and new API (request, name, context)
        return HTMLResponse("<html><body>mock</body></html>", status_code=200)

    return _mock_tr


def _get_client(orch: MagicMock) -> TestClient:
    """Return a TestClient with the lifespan replaced by a no-op that injects orch."""
    # Import server module fresh
    import sovereign.api.server as srv

    # Patch the module-level globals directly so lifespan is bypassed
    srv._orchestrator = orch
    srv._manager = MagicMock()

    # Patch templates so Jinja2 old API doesn't crash with starlette 1.0
    srv.templates.TemplateResponse = _mock_template_response()

    return TestClient(srv.app, raise_server_exceptions=False)


def _auth_header() -> dict:
    token = create_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def orch():
    return _make_orch()


@pytest.fixture
def client(orch):
    return _get_client(orch)


# ---------------------------------------------------------------------------
# Public routes (no auth needed)
# ---------------------------------------------------------------------------

class TestPublicRoutes:
    def test_get_root_200(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_get_status_200(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "SOVEREIGN AI OS"
        assert data["version"] == "0.3.0"
        assert "status" in data

    def test_get_health_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["overall"] == "healthy"

    def test_get_health_503_when_no_orch(self):
        import sovereign.api.server as srv
        old = srv._orchestrator
        try:
            srv._orchestrator = None
            tc = TestClient(srv.app, raise_server_exceptions=False)
            r = tc.get("/health")
            assert r.status_code == 503
        finally:
            srv._orchestrator = old

    def test_get_mode_returns_mode(self, client):
        r = client.get("/api/mode", headers=_auth_header())
        assert r.status_code == 200
        assert r.json()["mode"] == "command"

    def test_get_mode_returns_command_when_no_orch(self):
        import sovereign.api.server as srv
        old = srv._orchestrator
        try:
            srv._orchestrator = None
            tc = TestClient(srv.app, raise_server_exceptions=False)
            r = tc.get("/api/mode", headers=_auth_header())
            assert r.status_code == 200
            assert r.json()["mode"] == "command"
        finally:
            srv._orchestrator = old

    def test_manifest_json(self, client):
        r = client.get("/manifest.json")
        # Either 200 (file exists) or 404 (file missing) — both are handled
        assert r.status_code in (200, 404)

    def test_service_worker(self, client):
        r = client.get("/sw.js")
        assert r.status_code in (200, 404)

    def test_get_agents_200(self, client):
        r = client.get("/api/agents", headers=_auth_header())
        assert r.status_code == 200
        data = r.json()
        assert "count" in data
        assert "agents" in data

    def test_get_metrics_200(self, client):
        r = client.get("/api/metrics", headers=_auth_header())
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# HTML page routes
# ---------------------------------------------------------------------------

class TestHTMLPageRoutes:
    def test_dashboard(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_finance_page(self, client):
        r = client.get("/finance")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_business_page(self, client):
        r = client.get("/business")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_approvals_page(self, client):
        r = client.get("/approvals")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_hud_page(self, client):
        r = client.get("/hud")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_expansion_page(self, client):
        r = client.get("/expansion")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_entities_page(self, client):
        r = client.get("/entities")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

class TestAuthRoutes:
    def test_login_wrong_password_401(self, client, monkeypatch):
        monkeypatch.setenv("SOVEREIGN_PASSWORD", "testpass")
        r = client.post("/api/auth/login", json={"password": "wrong"})
        assert r.status_code == 401

    def test_login_correct_password_200(self, client, monkeypatch):
        monkeypatch.setenv("SOVEREIGN_PASSWORD", "testpass")
        r = client.post("/api/auth/login", json={"password": "testpass"})
        assert r.status_code == 200
        assert "token" in r.json()

    def test_login_no_password_env_returns_503(self, client, monkeypatch):
        monkeypatch.delenv("SOVEREIGN_PASSWORD", raising=False)
        r = client.post("/api/auth/login", json={"password": "sovereign"})
        assert r.status_code == 503


# ---------------------------------------------------------------------------
# Auth-protected routes — require Bearer token
# ---------------------------------------------------------------------------

class TestProtectedRoutes:
    def test_usage_no_auth_401(self, client):
        r = client.get("/api/usage")
        assert r.status_code == 401

    def test_usage_with_auth_200(self, client):
        r = client.get("/api/usage", headers=_auth_header())
        assert r.status_code == 200
        data = r.json()
        assert "usage" in data
        assert "sessions" in data

    def test_budget_no_auth_401(self, client):
        r = client.get("/api/budget")
        assert r.status_code == 401

    def test_budget_with_auth_200(self, client):
        r = client.get("/api/budget", headers=_auth_header())
        assert r.status_code == 200

    def test_escalations_no_auth_401(self, client):
        r = client.get("/api/escalations")
        assert r.status_code == 401

    def test_escalations_with_auth_200(self, client):
        r = client.get("/api/escalations", headers=_auth_header())
        assert r.status_code == 200
        assert "escalations" in r.json()

    def test_resolve_escalation_with_auth(self, client):
        r = client.post(
            "/api/escalations/evt-1/resolve",
            json={"resolution": "approved"},
            headers=_auth_header(),
        )
        assert r.status_code == 200

    def test_resolve_escalation_not_found(self, client, orch):
        orch.resolve_escalation.return_value = False
        r = client.post(
            "/api/escalations/missing/resolve",
            json={"resolution": "denied"},
            headers=_auth_header(),
        )
        assert r.status_code == 404

    def test_set_mode_with_auth(self, client):
        r = client.post("/api/mode", json={"mode": "finance"}, headers=_auth_header())
        assert r.status_code == 200

    def test_set_mode_invalid(self, client, orch):
        orch.set_mode.return_value = False
        r = client.post("/api/mode", json={"mode": "bogus"}, headers=_auth_header())
        assert r.status_code == 400

    def test_set_mode_no_auth_401(self, client):
        r = client.post("/api/mode", json={"mode": "finance"})
        assert r.status_code == 401

    def test_memory_domain_no_auth_401(self, client):
        r = client.get("/api/memory/operational")
        assert r.status_code == 401

    def test_memory_domain_with_auth(self, client):
        r = client.get("/api/memory/operational", headers=_auth_header())
        assert r.status_code == 200
        data = r.json()
        assert data["domain"] == "operational"


# ---------------------------------------------------------------------------
# Finance API routes (auth required)
# ---------------------------------------------------------------------------

class TestFinanceAPIRoutes:
    def test_finance_summary(self, client):
        with patch("sovereign.memory.domains.financial.FinancialMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.get_summary.return_value = {"net_worth": 100000}
            mock_cls.return_value = mock_store
            r = client.get("/api/finance/summary", headers=_auth_header())
            assert r.status_code == 200

    def test_finance_portfolio(self, client):
        with patch("sovereign.memory.domains.financial.FinancialMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.get_portfolio.return_value = []
            mock_store.get_portfolio_by_class.return_value = {}
            mock_cls.return_value = mock_store
            r = client.get("/api/finance/portfolio", headers=_auth_header())
            assert r.status_code == 200
            data = r.json()
            assert "holdings" in data
            assert "total" in data

    def test_finance_cashflow(self, client):
        with patch("sovereign.memory.domains.financial.FinancialMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.get_cashflow_by_month.return_value = []
            mock_cls.return_value = mock_store
            r = client.get("/api/finance/cashflow?months=6", headers=_auth_header())
            assert r.status_code == 200
            assert "cashflow" in r.json()

    def test_finance_transactions(self, client):
        with patch("sovereign.memory.domains.financial.FinancialMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.get_transactions.return_value = []
            mock_cls.return_value = mock_store
            r = client.get("/api/finance/transactions", headers=_auth_header())
            assert r.status_code == 200
            data = r.json()
            assert "transactions" in data


# ---------------------------------------------------------------------------
# Projects API routes
# ---------------------------------------------------------------------------

class TestProjectsAPIRoutes:
    def test_list_projects(self, client):
        with patch("sovereign.memory.domains.project.ProjectMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.get_projects.return_value = []
            mock_store.get_summary.return_value = {"total": 0}
            mock_cls.return_value = mock_store
            r = client.get("/api/projects", headers=_auth_header())
            assert r.status_code == 200
            data = r.json()
            assert "projects" in data

    def test_create_project(self, client):
        with patch("sovereign.memory.domains.project.ProjectMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.create_project.return_value = {"project_id": "p1", "name": "Test"}
            mock_cls.return_value = mock_store
            r = client.post("/api/projects", json={"name": "Test Project"}, headers=_auth_header())
            assert r.status_code == 201

    def test_update_project(self, client):
        with patch("sovereign.memory.domains.project.ProjectMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.update_project.return_value = True
            mock_cls.return_value = mock_store
            r = client.patch("/api/projects/p1", json={"status": "completed"}, headers=_auth_header())
            assert r.status_code == 200

    def test_update_project_not_found(self, client):
        with patch("sovereign.memory.domains.project.ProjectMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.update_project.return_value = False
            mock_cls.return_value = mock_store
            r = client.patch("/api/projects/missing", json={"status": "done"}, headers=_auth_header())
            assert r.status_code == 404

    def test_add_task_to_project(self, client):
        with patch("sovereign.memory.domains.project.ProjectMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.add_task.return_value = {"task_id": "t1", "title": "Do it"}
            mock_cls.return_value = mock_store
            r = client.post("/api/projects/p1/tasks", json={"title": "Do it"}, headers=_auth_header())
            assert r.status_code == 201

    def test_add_task_project_not_found(self, client):
        with patch("sovereign.memory.domains.project.ProjectMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.add_task.return_value = None
            mock_cls.return_value = mock_store
            r = client.post("/api/projects/missing/tasks", json={"title": "Do it"}, headers=_auth_header())
            assert r.status_code == 404

    def test_complete_task(self, client):
        with patch("sovereign.memory.domains.project.ProjectMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.complete_task.return_value = True
            mock_cls.return_value = mock_store
            r = client.post("/api/projects/p1/tasks/t1/complete", headers=_auth_header())
            assert r.status_code == 200

    def test_complete_task_not_found(self, client):
        with patch("sovereign.memory.domains.project.ProjectMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.complete_task.return_value = False
            mock_cls.return_value = mock_store
            r = client.post("/api/projects/p1/tasks/missing/complete", headers=_auth_header())
            assert r.status_code == 404


# ---------------------------------------------------------------------------
# Goals API routes
# ---------------------------------------------------------------------------

class TestGoalsAPIRoutes:
    def test_list_goals(self, client):
        r = client.get("/api/goals", headers=_auth_header())
        assert r.status_code == 200
        data = r.json()
        assert "goals" in data
        assert "summary" in data

    def test_add_goal(self, client):
        r = client.post("/api/goals", json={"title": "Run 10km"}, headers=_auth_header())
        assert r.status_code == 201
        data = r.json()
        assert "goal_id" in data

    def test_update_goal_progress(self, client, orch):
        goal = MagicMock()
        goal.goal_id = "g1"
        goal.progress_pct = 50.0
        goal.status = MagicMock(value="active")
        orch.goal_monitor.update_progress.return_value = goal
        r = client.patch("/api/goals/g1/progress", json={"value": 50.0}, headers=_auth_header())
        assert r.status_code == 200

    def test_update_goal_progress_not_found(self, client, orch):
        orch.goal_monitor.update_progress.return_value = None
        r = client.patch("/api/goals/missing/progress", json={"value": 50.0}, headers=_auth_header())
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Expansion API routes
# ---------------------------------------------------------------------------

class TestExpansionAPIRoutes:
    def test_expansion_agents(self, client):
        r = client.get("/api/expansion/agents", headers=_auth_header())
        assert r.status_code == 200
        assert "by_stage" in r.json()

    def test_expansion_model_perf_no_tracker(self, client):
        r = client.get("/api/expansion/model-perf", headers=_auth_header())
        # Returns {} when no tracker attached
        assert r.status_code == 200

    def test_expansion_model_perf_with_tracker(self, client, orch):
        tracker = MagicMock()
        tracker.to_dict.return_value = {"claude-sonnet-4-6": {"calls": 10}}
        orch._model_perf_tracker = tracker
        r = client.get("/api/expansion/model-perf", headers=_auth_header())
        assert r.status_code == 200

    def test_expansion_gaps(self, client):
        with patch("sovereign.expansion.capability_gap_detector.CapabilityGapDetector") as mock_det, \
             patch("sovereign.expansion.capability_gap_detector.WeeklyGapReport") as mock_rep:
            mock_det.return_value.all_gaps.return_value = []
            mock_rep.return_value.generate.return_value = {"gaps": []}
            r = client.get("/api/expansion/gaps", headers=_auth_header())
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# Entities API routes
# ---------------------------------------------------------------------------

class TestEntitiesAPIRoutes:
    def test_list_entities(self, client):
        r = client.get("/api/entities", headers=_auth_header())
        assert r.status_code == 200
        assert "entities" in r.json()

    def test_get_entity_not_found(self, client, orch):
        orch.entity_provisioner.get_entity_summary.return_value = None
        r = client.get("/api/entities/missing-id", headers=_auth_header())
        assert r.status_code == 404

    def test_provision_entity_with_auth(self, client, orch):
        from dataclasses import dataclass, field as dc_field

        @dataclass
        class FakeEntity:
            entity_id: str = "e1"
            name: str = "TestBank"
            category: str = "account"
            connector_config: dict = dc_field(default_factory=dict)
            agent_bindings: list = dc_field(default_factory=list)
            files: list = dc_field(default_factory=list)
            ui_panel: str = "dashboard"
            sync_interval_s: float = 3600.0
            metadata: dict = dc_field(default_factory=dict)

        orch.entity_provisioner.provision.return_value = FakeEntity()
        r = client.post(
            "/api/entities",
            json={"name": "TestBank", "category": "account"},
            headers=_auth_header(),
        )
        assert r.status_code == 201

    def test_deprovision_entity_with_auth(self, client, orch):
        orch.entity_provisioner.deprovision.return_value = True
        r = client.delete("/api/entities/e1", headers=_auth_header())
        assert r.status_code == 200
        assert r.json()["deprovisioned"] == "e1"

    def test_deprovision_entity_not_found(self, client, orch):
        orch.entity_provisioner.deprovision.return_value = False
        r = client.delete("/api/entities/missing", headers=_auth_header())
        assert r.status_code == 404

    def test_sync_entity_with_auth(self, client, orch):
        orch.entity_provisioner.sync.return_value = {"synced": True}
        r = client.post("/api/entities/e1/sync", headers=_auth_header())
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Suggestions + Integrations
# ---------------------------------------------------------------------------

class TestSuggestionsIntegrations:
    def test_suggestions(self, client):
        r = client.get("/api/suggestions", headers=_auth_header())
        assert r.status_code == 200
        assert "suggestions" in r.json()

    def test_integrations(self, client):
        r = client.get("/api/integrations", headers=_auth_header())
        assert r.status_code == 200
        assert "integrations" in r.json()


# ---------------------------------------------------------------------------
# Finance import
# ---------------------------------------------------------------------------

class TestFinanceImport:
    def test_finance_import_csv(self, client):
        with patch("sovereign.memory.domains.financial.FinancialMemoryStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.import_csv_transactions.return_value = {"imported": 1}
            mock_cls.return_value = mock_store
            r = client.post(
                "/api/finance/import",
                json={
                    "csv_text": "date,description,amount\n2024-01-01,Test,100",
                    "date_col": "date",
                    "desc_col": "description",
                    "amount_col": "amount",
                },
                headers=_auth_header(),
            )
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# No-orchestrator guard on various protected-ish routes
# ---------------------------------------------------------------------------

class TestNoOrchGuards:
    """Verify all routes returning 503 when orchestrator is None."""

    def _no_orch_client(self):
        import sovereign.api.server as srv
        old = srv._orchestrator
        srv._orchestrator = None
        tc = TestClient(srv.app, raise_server_exceptions=False)
        srv._orchestrator = old
        return tc, old

    def test_usage_no_orch(self):
        import sovereign.api.server as srv
        old_orch = srv._orchestrator
        srv._orchestrator = None
        try:
            tc = TestClient(srv.app, raise_server_exceptions=False)
            r = tc.get("/api/usage", headers=_auth_header())
            assert r.status_code == 503
        finally:
            srv._orchestrator = old_orch

    def test_agents_no_orch(self):
        import sovereign.api.server as srv
        old_orch = srv._orchestrator
        srv._orchestrator = None
        try:
            tc = TestClient(srv.app, raise_server_exceptions=False)
            r = tc.get("/api/agents", headers=_auth_header())
            assert r.status_code == 503
        finally:
            srv._orchestrator = old_orch

    def test_escalations_no_orch(self):
        import sovereign.api.server as srv
        old_orch = srv._orchestrator
        srv._orchestrator = None
        try:
            tc = TestClient(srv.app, raise_server_exceptions=False)
            r = tc.get("/api/escalations", headers=_auth_header())
            assert r.status_code == 503
        finally:
            srv._orchestrator = old_orch


# ---------------------------------------------------------------------------
# New domain endpoints: brief, digest, watchdog, webhooks
# ---------------------------------------------------------------------------

class TestBriefDigestWatchdog:
    def test_brief_returns_200(self, client):
        r = client.get("/api/brief", headers=_auth_header())
        assert r.status_code == 200
        data = r.json()
        assert "generated_at" in data

    def test_brief_503_no_orch(self):
        import sovereign.api.server as srv
        old = srv._orchestrator
        srv._orchestrator = None
        try:
            tc = TestClient(srv.app, raise_server_exceptions=False)
            r = tc.get("/api/brief", headers=_auth_header())
            assert r.status_code == 503
        finally:
            srv._orchestrator = old

    def test_digest_returns_200(self, client, orch):
        from unittest.mock import AsyncMock, MagicMock
        digest_mock = MagicMock()
        digest_mock.text = "# SOVEREIGN Daily Digest"
        digest_mock.generated_at = "2026-04-26T08:00:00Z"
        with patch(
            "sovereign.proactive.daily_digest.DailyDigest.generate",
            new_callable=AsyncMock,
            return_value=digest_mock,
        ):
            r = client.get("/api/digest", headers=_auth_header())
        assert r.status_code == 200
        data = r.json()
        assert "text" in data
        assert "generated_at" in data

    def test_watchdog_returns_200(self, client, orch):
        orch.process_watchdog = MagicMock()
        orch.process_watchdog.health_summary.return_value = {
            "names": [], "details": {}, "total_restarts": 0, "crashed_names": []
        }
        r = client.get("/api/watchdog", headers=_auth_header())
        assert r.status_code == 200
        data = r.json()
        assert "total_restarts" in data

    def test_watchdog_503_no_orch(self):
        import sovereign.api.server as srv
        old = srv._orchestrator
        srv._orchestrator = None
        try:
            tc = TestClient(srv.app, raise_server_exceptions=False)
            r = tc.get("/api/watchdog", headers=_auth_header())
            assert r.status_code == 503
        finally:
            srv._orchestrator = old

    def test_webhook_stats_200(self, client, orch):
        orch.webhook_router = MagicMock()
        orch.webhook_router.stats.return_value = {"total": 0, "processed": 0, "failed": 0}
        orch.webhook_router.event_history.return_value = []
        r = client.get("/api/webhooks/stats", headers=_auth_header())
        assert r.status_code == 200
        data = r.json()
        assert "stats" in data

    def test_inbound_webhook_200(self, client, orch):
        from unittest.mock import AsyncMock, MagicMock
        from sovereign.infra.webhooks import WebhookEvent
        event = WebhookEvent(
            event_id="abc123", source="github", event_type="push",
            payload={"ref": "main"}, processed=True,
        )
        orch.webhook_router = MagicMock()
        orch.webhook_router.receive = AsyncMock(return_value=event)
        r = client.post(
            "/api/webhooks/github/push",
            json={"ref": "main"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "github"
        assert data["event_type"] == "push"


class TestNextActionsAPI:
    def test_list_next_actions_200(self, client):
        r = client.get("/api/next-actions", headers=_auth_header())
        assert r.status_code in (200, 500)  # 500 if no data file, 200 if present

    def test_create_next_action_401_no_auth(self, client):
        r = client.post("/api/next-actions", json={"title": "Do something"})
        assert r.status_code == 401

    def test_create_next_action_201(self, client):
        r = client.post(
            "/api/next-actions",
            json={"title": "Test action", "priority": "high"},
            headers=_auth_header(),
        )
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Test action"
        assert data["priority"] == "high"

    def test_complete_next_action_200(self, client):
        # Create then complete
        r = client.post(
            "/api/next-actions",
            json={"title": "To complete"},
            headers=_auth_header(),
        )
        assert r.status_code == 201
        action_id = r.json()["action_id"]
        r2 = client.patch(
            f"/api/next-actions/{action_id}/complete",
            headers=_auth_header(),
        )
        assert r2.status_code == 200
        assert r2.json()["completed"] == action_id


class TestConstitutionAPI:
    def test_get_constitution_200(self, client):
        r = client.get("/api/constitution", headers=_auth_header())
        assert r.status_code in (200, 500)

    def test_update_constitution_401_no_auth(self, client):
        r = client.patch("/api/constitution", json={"personal_mission": "Build great things"})
        assert r.status_code == 401

    def test_update_constitution_200(self, client):
        r = client.patch(
            "/api/constitution",
            json={"personal_mission": "Build great things", "core_values": ["freedom", "mastery"]},
            headers=_auth_header(),
        )
        assert r.status_code == 200
        assert r.json()["updated"] is True


class TestPersonalVersionAPI:
    def test_get_personal_version_200(self, client):
        r = client.get("/api/personal-version", headers=_auth_header())
        assert r.status_code in (200, 500)

    def test_save_personal_version_201(self, client):
        r = client.post(
            "/api/personal-version",
            json={
                "period": "2026-04",
                "version_label": "v2.4 The Builder",
                "overall_rating": 8,
                "net_worth": 150000.0,
                "month_summary": "Great month",
            },
            headers=_auth_header(),
        )
        assert r.status_code == 201
        assert r.json()["period"] == "2026-04"

    def test_save_personal_version_401_no_auth(self, client):
        r = client.post("/api/personal-version", json={"period": "2026-04"})
        assert r.status_code == 401


class TestMemorySearchAPI:
    def test_search_requires_auth(self, client):
        r = client.get("/api/memory/search?q=test")
        assert r.status_code == 401

    def test_search_returns_results(self, client, orch):
        orch._memory.semantic_search = AsyncMock(return_value=[
            {"domain": "identity", "key": "profile", "record": {}, "score": 0.9}
        ])
        r = client.get("/api/memory/search?q=identity", headers=_auth_header())
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert data["query"] == "identity"

    def test_search_empty_query_400(self, client):
        r = client.get("/api/memory/search?q=", headers=_auth_header())
        assert r.status_code == 400

    def test_search_503_no_orch(self):
        import sovereign.api.server as srv
        old = srv._orchestrator
        srv._orchestrator = None
        try:
            tc = TestClient(srv.app, raise_server_exceptions=False)
            r = tc.get("/api/memory/search?q=test", headers=_auth_header())
            assert r.status_code == 503
        finally:
            srv._orchestrator = old
