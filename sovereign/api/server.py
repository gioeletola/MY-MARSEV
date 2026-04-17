"""
SOVEREIGN AI OS — FastAPI web server.

Exposes:
  GET  /          → single-page UI (Jinja2 template)
  WS   /ws        → WebSocket for real-time streaming
  GET  /health    → JSON system health check
  GET  /api/usage → token usage summary
"""
from __future__ import annotations

import logging
import os
import pathlib
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from sovereign.api.ws_handler import WebSocketSessionManager

logger = logging.getLogger(__name__)

# Paths
_HERE = pathlib.Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"

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
        logger.info("SOVEREIGN AI OS web server started")
    except Exception as exc:
        logger.error("Failed to start orchestrator", error=str(exc))
        raise
    yield
    logger.info("SOVEREIGN AI OS web server shutting down")


app = FastAPI(
    title="SOVEREIGN AI OS",
    description="Multi-agent orchestration operating system — web interface",
    version="0.2.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Routes
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
async def usage() -> JSONResponse:
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
