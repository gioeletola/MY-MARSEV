"""
SOVEREIGN AI OS — FastAPI web server.

Exposes:
  GET  /                               → single-page UI (Jinja2 template)
  WS   /ws                             → WebSocket for real-time streaming
  GET  /health                         → JSON system health check
  GET  /api/usage                      → token usage summary
  GET  /api/budget                     → daily / monthly budget summary
  GET  /api/escalations                → pending escalation events
  POST /api/escalations/{id}/resolve   → resolve an escalation event
  GET  /api/agents                     → registered agent list
  GET  /api/metrics                    → live session metrics
"""
from __future__ import annotations

import logging
import os
import pathlib
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from sovereign.api.auth import create_token, require_auth
from sovereign.api.ws_handler import WebSocketSessionManager

logger = logging.getLogger(__name__)

# Paths
_HERE = pathlib.Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"

# Global singletons (initialised in lifespan)
_orchestrator: Any = None
_manager: WebSocketSessionManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create orchestrator and WS session manager. Shutdown: log."""
    global _orchestrator, _manager
    config_path = os.environ.get("SOVEREIGN_CONFIG", "config/sovereign.yaml")
    try:
        from sovereign.bootstrap import create_orchestrator
        _orchestrator = create_orchestrator(config_path)
        _manager = WebSocketSessionManager(_orchestrator)
        await _orchestrator.start_background_tasks()
        logger.info("SOVEREIGN AI OS web server started")
    except Exception as exc:
        logger.error("Failed to start orchestrator", error=str(exc))
        raise
    try:
        yield
    finally:
        await _orchestrator.stop_background_tasks()
        logger.info("SOVEREIGN AI OS web server shutting down")


app = FastAPI(
    title="SOVEREIGN AI OS",
    description="Multi-agent orchestration operating system — web interface",
    version="0.2.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Serve PWA static assets (manifest.json, sw.js)
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Public routes (no auth required)
# ---------------------------------------------------------------------------

@app.post("/api/auth/login")
async def login(request: Request) -> JSONResponse:
    """Issue a JWT. Body: {"password": "<SOVEREIGN_PASSWORD env var>"}."""
    import os
    body = await request.json()
    password = body.get("password", "")
    expected = os.environ.get("SOVEREIGN_PASSWORD", "sovereign")
    if password != expected:
        return JSONResponse({"error": "Invalid password"}, status_code=401)
    token = create_token({"sub": "admin", "role": "admin"})
    return JSONResponse({"token": token})


@app.get("/api/status")
async def public_status() -> JSONResponse:
    """Public health/status — no auth required."""
    import platform
    return JSONResponse({
        "service": "SOVEREIGN AI OS",
        "version": "0.2.0",
        "status": "online" if _orchestrator is not None else "initialising",
        "python": platform.python_version(),
    })


@app.get("/manifest.json")
async def pwa_manifest() -> FileResponse:
    """PWA web app manifest."""
    path = _STATIC_DIR / "manifest.json"
    if path.exists():
        return FileResponse(str(path), media_type="application/manifest+json")
    return JSONResponse({"error": "manifest not found"}, status_code=404)


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    """PWA service worker."""
    path = _STATIC_DIR / "sw.js"
    if path.exists():
        return FileResponse(
            str(path),
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/"},
        )
    return JSONResponse({"error": "service worker not found"}, status_code=404)


# ---------------------------------------------------------------------------
# Main UI (public — auth handled client-side via WS token)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """Serve the single-page UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Real-time bidirectional channel for agent streaming."""
    await ws.accept()
    if _manager is None:
        await ws.send_json({"type": "error", "message": "Server not ready"})
        await ws.close()
        return
    try:
        await _manager.handle(ws)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("WebSocket error", error=str(exc))


@app.get("/health")
async def health() -> JSONResponse:
    """JSON system health check."""
    if _orchestrator is None:
        return JSONResponse({"overall": "critical", "error": "Not initialised"}, status_code=503)
    return JSONResponse(_orchestrator.health())


@app.get("/api/usage")
async def usage(_: dict = Depends(require_auth)) -> JSONResponse:
    """Token usage statistics."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    return JSONResponse({
        "usage": _orchestrator.get_usage(),
        "sessions": _orchestrator.get_session_count(),
    })


@app.get("/dashboard", response_class=HTMLResponse)
async def executive_dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("executive_dashboard.html", {"request": request})


@app.get("/finance", response_class=HTMLResponse)
async def finance_cockpit(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("finance_cockpit.html", {"request": request})


@app.get("/business", response_class=HTMLResponse)
async def business_wall(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("business_wall.html", {"request": request})


@app.get("/approvals", response_class=HTMLResponse)
async def approvals_center(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("approvals_center.html", {"request": request})


@app.get("/hud", response_class=HTMLResponse)
async def jarvis_hud(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("jarvis_hud.html", {"request": request})


# ---------------------------------------------------------------------------
# REST API — governance / observability
# ---------------------------------------------------------------------------

@app.get("/api/budget")
async def budget(_: dict = Depends(require_auth)) -> JSONResponse:
    """Daily and monthly token / cost budget summary."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    return JSONResponse(_orchestrator.get_budget_summary())


@app.get("/api/escalations")
async def list_escalations(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return all pending escalation events."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    return JSONResponse({"escalations": _orchestrator.get_pending_escalations()})


class ResolveRequest(BaseModel):
    resolution: str = "approved"


@app.post("/api/escalations/{event_id}/resolve")
async def resolve_escalation(event_id: str, body: ResolveRequest, _: dict = Depends(require_auth)) -> JSONResponse:
    """Resolve an escalation event by ID."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    success = _orchestrator.resolve_escalation(event_id, body.resolution)
    if not success:
        return JSONResponse({"error": "Event not found or already resolved"}, status_code=404)
    return JSONResponse({"resolved": event_id, "resolution": body.resolution})


@app.get("/api/agents")
async def list_agents() -> JSONResponse:
    """Return count and summary of registered agents."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    registry = _orchestrator._agent_registry
    agents = registry.list_agents()
    return JSONResponse({"count": registry.count(), "agents": agents})


@app.get("/api/metrics")
async def metrics() -> JSONResponse:
    """Live session experiment metrics."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    return JSONResponse(_orchestrator.get_experiment_metrics("live_sessions"))


# ---------------------------------------------------------------------------
# REST API — Finance (V2)
# ---------------------------------------------------------------------------

@app.get("/api/finance/summary")
async def finance_summary() -> JSONResponse:
    """Finance KPI summary: net worth, cashflow, portfolio total."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.financial import FinancialMemoryStore
        store = FinancialMemoryStore()
        return JSONResponse(store.get_summary())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/finance/transactions")
async def finance_transactions(limit: int = 50, date_from: str = "", date_to: str = "", category: str = "") -> JSONResponse:
    """Recent transactions with optional filters."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.financial import FinancialMemoryStore
        store = FinancialMemoryStore()
        txs = store.get_transactions(limit=limit, date_from=date_from, date_to=date_to, category=category)
        return JSONResponse({"transactions": txs, "count": len(txs)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/finance/portfolio")
async def finance_portfolio() -> JSONResponse:
    """Portfolio holdings by asset class."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.financial import FinancialMemoryStore
        store = FinancialMemoryStore()
        return JSONResponse({
            "holdings": store.get_portfolio(),
            "by_class": store.get_portfolio_by_class(),
            "total": sum(float(h.get("value", 0)) for h in store.get_portfolio()),
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/finance/cashflow")
async def finance_cashflow(months: int = 12) -> JSONResponse:
    """Monthly cashflow bars for the last N months."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.financial import FinancialMemoryStore
        store = FinancialMemoryStore()
        return JSONResponse({"cashflow": store.get_cashflow_by_month(months=months)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class ImportCSVRequest(BaseModel):
    csv_text:   str
    date_col:   str = "date"
    desc_col:   str = "description"
    amount_col: str = "amount"


@app.post("/api/finance/import")
async def finance_import_csv(body: ImportCSVRequest) -> JSONResponse:
    """Import bank statement CSV into the financial memory store."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.financial import FinancialMemoryStore
        store = FinancialMemoryStore()
        result = store.import_csv_transactions(
            body.csv_text,
            date_col=body.date_col,
            desc_col=body.desc_col,
            amount_col=body.amount_col,
        )
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Projects (V2)
# ---------------------------------------------------------------------------

@app.get("/api/projects")
async def list_projects(status: str = "") -> JSONResponse:
    """Return all projects, optionally filtered by status."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.project import ProjectMemoryStore
        store = ProjectMemoryStore()
        projects = store.get_projects(status=status)
        summary  = store.get_summary()
        return JSONResponse({"projects": projects, "summary": summary})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class CreateProjectRequest(BaseModel):
    name:        str
    description: str = ""
    status:      str = "active"
    owner:       str = ""
    deadline:    str = ""
    tags:        list[str] = []


@app.post("/api/projects")
async def create_project(body: CreateProjectRequest) -> JSONResponse:
    """Create a new project."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.project import ProjectMemoryStore
        store   = ProjectMemoryStore()
        project = store.create_project(
            name=body.name, description=body.description,
            status=body.status, owner=body.owner,
            deadline=body.deadline, tags=body.tags,
        )
        return JSONResponse(project, status_code=201)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class UpdateProjectRequest(BaseModel):
    name:        str | None = None
    description: str | None = None
    status:      str | None = None
    progress:    int | None = None
    owner:       str | None = None
    deadline:    str | None = None


@app.patch("/api/projects/{project_id}")
async def update_project(project_id: str, body: UpdateProjectRequest) -> JSONResponse:
    """Update a project's fields."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.project import ProjectMemoryStore
        store   = ProjectMemoryStore()
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        ok      = store.update_project(project_id, **updates)
        if not ok:
            return JSONResponse({"error": "Project not found"}, status_code=404)
        return JSONResponse({"updated": project_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class AddTaskRequest(BaseModel):
    title:    str
    assignee: str = ""
    due_date: str = ""
    priority: int = 2
    notes:    str = ""


@app.post("/api/projects/{project_id}/tasks")
async def add_task(project_id: str, body: AddTaskRequest) -> JSONResponse:
    """Add a task to a project."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.project import ProjectMemoryStore
        store = ProjectMemoryStore()
        task  = store.add_task(project_id, body.title, body.assignee, body.due_date, body.priority, body.notes)
        if task is None:
            return JSONResponse({"error": "Project not found"}, status_code=404)
        return JSONResponse(task, status_code=201)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/projects/{project_id}/tasks/{task_id}/complete")
async def complete_task(project_id: str, task_id: str) -> JSONResponse:
    """Mark a task as complete."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.memory.domains.project import ProjectMemoryStore
        store = ProjectMemoryStore()
        ok    = store.complete_task(project_id, task_id)
        if not ok:
            return JSONResponse({"error": "Project or task not found"}, status_code=404)
        return JSONResponse({"completed": task_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Goals (V2)
# ---------------------------------------------------------------------------

@app.get("/api/goals")
async def list_goals() -> JSONResponse:
    """Return all active goals and a summary."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        monitor = _orchestrator.goal_monitor
        goals   = [
            {
                "goal_id":      g.goal_id,
                "title":        g.title,
                "description":  g.description,
                "target_value": g.target_value,
                "current_value":g.current_value,
                "unit":         g.unit,
                "progress_pct": g.progress_pct,
                "status":       g.status.value,
                "is_overdue":   g.is_overdue,
                "deadline":     g.deadline,
                "tags":         g.tags,
            }
            for g in monitor.active_goals()
        ]
        return JSONResponse({"goals": goals, "summary": monitor.summary()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class AddGoalRequest(BaseModel):
    title:        str
    description:  str   = ""
    target_value: float = 100.0
    unit:         str   = ""
    deadline:     float = 0.0
    tags:         list[str] = []


@app.post("/api/goals")
async def add_goal(body: AddGoalRequest) -> JSONResponse:
    """Add a new goal to the GoalMonitor."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        import uuid
        from sovereign.proactive.goal_monitor import Goal
        monitor = _orchestrator.goal_monitor
        goal = Goal(
            goal_id=str(uuid.uuid4())[:8],
            title=body.title,
            description=body.description,
            target_value=body.target_value,
            unit=body.unit,
            deadline=body.deadline,
            tags=body.tags,
        )
        monitor.add(goal)
        return JSONResponse({"goal_id": goal.goal_id, "title": goal.title}, status_code=201)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class UpdateProgressRequest(BaseModel):
    value: float


@app.patch("/api/goals/{goal_id}/progress")
async def update_goal_progress(goal_id: str, body: UpdateProgressRequest) -> JSONResponse:
    """Update a goal's current progress value."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        monitor = _orchestrator.goal_monitor
        goal    = monitor.update_progress(goal_id, body.value)
        if goal is None:
            return JSONResponse({"error": "Goal not found"}, status_code=404)
        return JSONResponse({
            "goal_id":     goal.goal_id,
            "progress_pct":goal.progress_pct,
            "status":      goal.status.value,
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Suggestions & Integrations (V2)
# ---------------------------------------------------------------------------

@app.get("/api/suggestions")
async def list_suggestions() -> JSONResponse:
    """Return current proactive suggestions from SuggestionEngine."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        engine  = _orchestrator.suggestion_engine
        snap    = await _orchestrator._memory.get_snapshot(domains=["financial","project","operational"])
        suggestions = engine.evaluate(snap)
        return JSONResponse({"suggestions": [
            {
                "id":          s.suggestion_id,
                "title":       s.title,
                "description": s.description,
                "action":      s.action,
                "priority":    s.priority,
                "source":      s.source,
            }
            for s in suggestions
        ]})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/integrations")
async def list_integrations() -> JSONResponse:
    """Return status of all integration connectors."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        return JSONResponse({"integrations": _orchestrator.integration_manager.list_all()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Expansion (capability gaps + model performance)
# ---------------------------------------------------------------------------

@app.get("/expansion", response_class=HTMLResponse)
async def expansion_dashboard(request: Request) -> HTMLResponse:
    """Serve the Expansion Dashboard."""
    return templates.TemplateResponse("expansion_dashboard.html", {"request": request})


@app.get("/api/expansion/gaps")
async def expansion_gaps() -> JSONResponse:
    """Return top capability gaps from the CapabilityGapDetector."""
    try:
        from sovereign.expansion.capability_gap_detector import (
            CapabilityGapDetector,
            WeeklyGapReport,
        )
        detector = CapabilityGapDetector()
        all_gaps = detector.all_gaps()
        report = WeeklyGapReport().generate(all_gaps)
        return JSONResponse(report)
    except Exception as exc:
        logger.warning("expansion_gaps error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/expansion/agents")
async def expansion_agents() -> JSONResponse:
    """Return agents grouped by lifecycle stage (sandbox/shadow/production)."""
    if _orchestrator is None:
        return JSONResponse({"by_stage": {}})
    try:
        registry = _orchestrator._agent_registry
        agents = registry.list_agents()
        # Group by stage field if present, else bucket all into production
        by_stage: dict[str, list] = {}
        for a in agents:
            stage = a.get("stage", "production") if isinstance(a, dict) else "production"
            by_stage.setdefault(stage, []).append(a)
        return JSONResponse({"by_stage": by_stage, "total": registry.count()})
    except Exception as exc:
        logger.warning("expansion_agents error: %s", exc)
        return JSONResponse({"by_stage": {}, "error": str(exc)}, status_code=500)


@app.get("/api/expansion/model-perf")
async def expansion_model_perf() -> JSONResponse:
    """Return per-model performance metrics from ModelPerformanceTracker."""
    if _orchestrator is None:
        return JSONResponse({})
    try:
        tracker = getattr(_orchestrator, "_model_perf_tracker", None)
        if tracker is None:
            return JSONResponse({})
        return JSONResponse(tracker.to_dict())
    except Exception as exc:
        logger.warning("expansion_model_perf error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Connected Entities
# ---------------------------------------------------------------------------


class ProvisionEntityRequest(BaseModel):
    name: str
    category: str
    connector_config: dict | None = None
    agent_bindings: list[str] = []
    files: list[str] = []
    ui_panel: str = "dashboard"
    sync_interval_s: float = 3600.0
    metadata: dict = {}


class UpdateEntityRequest(BaseModel):
    status: str | None = None


@app.get("/entities", response_class=HTMLResponse)
async def entities_panel(request: Request) -> HTMLResponse:
    """Serve the Entities management panel."""
    return templates.TemplateResponse("entities_panel.html", {"request": request})


@app.get("/api/entities")
async def list_entities(category: str = "") -> JSONResponse:
    """Return all connected entities, optionally filtered by category."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        provisioner = _orchestrator.entity_provisioner
        entities = provisioner.list_entities(category=category)
        return JSONResponse({"entities": entities, "count": len(entities)})
    except Exception as exc:
        logger.warning("list_entities error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/entities")
async def provision_entity(
    body: ProvisionEntityRequest, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Provision a new connected entity (7-step pipeline)."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        provisioner = _orchestrator.entity_provisioner
        entity = provisioner.provision(
            name=body.name,
            category=body.category,
            connector_config=body.connector_config,
            agent_bindings=body.agent_bindings,
            files=body.files,
            ui_panel=body.ui_panel,
            sync_interval_s=body.sync_interval_s,
            metadata=body.metadata,
        )
        return JSONResponse(entity.to_dict(), status_code=201)
    except Exception as exc:
        logger.warning("provision_entity error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/entities/{entity_id}")
async def get_entity(entity_id: str) -> JSONResponse:
    """Return full summary for a single entity."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        provisioner = _orchestrator.entity_provisioner
        summary = provisioner.get_entity_summary(entity_id)
        if not summary:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        return JSONResponse(summary)
    except Exception as exc:
        logger.warning("get_entity error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.patch("/api/entities/{entity_id}")
async def update_entity(
    entity_id: str, body: UpdateEntityRequest, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Update entity fields (currently status)."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        registry = _orchestrator._entity_registry
        if body.status is not None:
            ok = registry.update_status(entity_id, body.status)
            if not ok:
                return JSONResponse({"error": "Entity not found"}, status_code=404)
        return JSONResponse({"updated": entity_id})
    except Exception as exc:
        logger.warning("update_entity error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/entities/{entity_id}/sync")
async def sync_entity(entity_id: str, _: dict = Depends(require_auth)) -> JSONResponse:
    """Trigger a manual sync for an entity."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        provisioner = _orchestrator.entity_provisioner
        result = provisioner.sync(entity_id)
        if not result.get("ok") and result.get("error"):
            return JSONResponse(result, status_code=200)
        return JSONResponse(result)
    except Exception as exc:
        logger.warning("sync_entity error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.delete("/api/entities/{entity_id}")
async def deprovision_entity(
    entity_id: str, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Deprovision an entity (removes vault, bindings, sync job)."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        provisioner = _orchestrator.entity_provisioner
        ok = provisioner.deprovision(entity_id)
        if not ok:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        return JSONResponse({"deprovisioned": entity_id})
    except Exception as exc:
        logger.warning("deprovision_entity error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)
