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

import asyncio
import collections
import logging
import os
import pathlib
import secrets as _secrets
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from sovereign import __version__
from sovereign.api.auth import (
    check_rate_limit, consume_ws_ticket, create_token, create_ws_ticket,
    require_auth, reset_rate_limit, revoke_token, verify_token,
)
from sovereign.api.ws_handler import WebSocketSessionManager

logger = logging.getLogger(__name__)

# Paths
_HERE = pathlib.Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"
_STATIC_DIR = _HERE / "static"

# Global singletons (initialised in lifespan)
_orchestrator: Any = None
_manager: WebSocketSessionManager | None = None

# ---------------------------------------------------------------------------
# Per-IP HTTP API rate limiter (all /api/* endpoints)
# ---------------------------------------------------------------------------
_api_rate_lock = threading.Lock()
_api_calls: dict[str, collections.deque] = {}
_API_RATE_MAX    = 120   # requests per window
_API_RATE_WINDOW = 60.0  # seconds


def _api_rate_check(ip: str) -> bool:
    """Sliding-window rate check for general API endpoints. Returns True if allowed."""
    now = time.monotonic()
    cutoff = now - _API_RATE_WINDOW
    with _api_rate_lock:
        if ip not in _api_calls:
            _api_calls[ip] = collections.deque()
        dq = _api_calls[ip]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= _API_RATE_MAX:
            return False
        dq.append(now)
        return True

# Voice singletons — lazily initialised on first use
_tts_engine: Any = None          # TTSEngine | None
_voice_recogniser: Any = None    # VoiceCommandRecogniser | None
_feedback_registry: Any = None   # AgentFeedbackRegistry | None


def _get_tts() -> Any:
    global _tts_engine
    if _tts_engine is None:
        from sovereign.hud.tts_engine import TTSEngine
        _tts_engine = TTSEngine()
    return _tts_engine


def _get_recogniser() -> Any:
    global _voice_recogniser
    if _voice_recogniser is None:
        import os
        from sovereign.hud.voice_command import VoiceCommandRecogniser
        _voice_recogniser = VoiceCommandRecogniser(api_key=os.environ.get("OPENAI_API_KEY", ""))
    return _voice_recogniser


def _get_feedback_registry() -> Any:
    global _feedback_registry
    if _feedback_registry is None:
        from sovereign.registries.agent_feedback import AgentFeedbackRegistry
        _feedback_registry = AgentFeedbackRegistry()
    return _feedback_registry


class _SchedulerQueueAdapter:
    """Wrap asyncio.Queue so the Scheduler's run_loop can call queue.enqueue(...)."""

    def __init__(self, q: asyncio.Queue) -> None:
        self._q = q

    async def enqueue(self, agent_id: str, objective: str, payload: dict | None = None) -> None:
        # We store a simple namespace so the consumer can read .job_id / .objective
        import types
        item = types.SimpleNamespace(
            job_id=agent_id,
            agent_id=agent_id,
            objective=objective,
            payload=payload or {},
        )
        await self._q.put(item)


async def _consume_scheduler_queue(queue: asyncio.Queue, orch: Any) -> None:
    """Drain the scheduler job queue and dispatch each job to the orchestrator."""
    while True:
        job = await queue.get()
        try:
            agent_id = getattr(job, "agent_id", None)
            if agent_id == "morning_loop":
                from sovereign.proactive.morning_loop import MorningLoop
                await MorningLoop(orchestrator=orch).run()
            elif agent_id == "memory_compaction":
                from sovereign.memory.compaction import MemoryCompaction
                mc = MemoryCompaction(getattr(orch, "_memory", None))
                await mc.run()
            elif agent_id == "eval_agent":
                from sovereign.registries.eval_agent import EvalAgent as _FeedbackEvalAgent
                ea = _FeedbackEvalAgent()
                results = await ea.run()
                if getattr(orch, "_memory", None):
                    await ea.report_to_memory(orch._memory, results)
            else:
                await orch.handle_request(job.objective)
            # Emit typed event so the ProactiveEventReactor can log it
            try:
                from sovereign.events.event_types import EventType, SovereignEvent
                orch.event_bus.emit(SovereignEvent(
                    type=EventType.JOB_COMPLETE,
                    data={"job_id": job.job_id, "name": getattr(job, "name", job.job_id)},
                ))
            except Exception:
                pass
        except Exception as exc:
            logger.error("Scheduled job %s failed: %s", job.job_id, exc)
        finally:
            queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create orchestrator, WS session manager, scheduler, and backup. Shutdown: clean up."""
    global _orchestrator, _manager
    from sovereign.api.auth import assert_production_ready
    assert_production_ready()
    config_path = os.environ.get("SOVEREIGN_CONFIG", "config/sovereign.yaml")
    try:
        from sovereign.bootstrap import create_orchestrator
        _orchestrator = create_orchestrator(config_path)
        _manager = WebSocketSessionManager(_orchestrator)
        await _orchestrator.start_background_tasks()

        # Memory seed: populate default identity/operational entries on first run
        try:
            from sovereign.memory.seed import run_seed
            await run_seed(_orchestrator._memory)
        except Exception as _exc:
            logger.warning("Memory seed failed: %s", _exc)

        # ── Proactive event reactor ────────────────────────────────────────
        try:
            from sovereign.proactive.event_reactor import ProactiveEventReactor
            _reactor = ProactiveEventReactor(_orchestrator)
            _reactor.attach(_orchestrator.event_bus)
            # Bind the event loop so async subscribers can be scheduled
            _orchestrator.event_bus.set_loop(asyncio.get_event_loop())
        except Exception as _exc:
            logger.warning("ProactiveEventReactor not started: %s", _exc)

        logger.info("SOVEREIGN AI OS web server started")
    except Exception as exc:
        logger.error("Failed to start orchestrator", error=str(exc))
        raise

    # ── Scheduler ─────────────────────────────────────────────────────────
    _scheduler_task: asyncio.Task | None = None
    _consumer_task: asyncio.Task | None = None
    _stop_event: asyncio.Event | None = None

    try:
        from sovereign.infra.scheduler import Scheduler
        _scheduler = Scheduler()
        _stop_event = asyncio.Event()
        _job_queue: asyncio.Queue = asyncio.Queue()
        _queue_adapter = _SchedulerQueueAdapter(_job_queue)
        _scheduler_task = asyncio.create_task(
            _scheduler.run_loop(_queue_adapter, _stop_event),
            name="scheduler_loop",
        )
        _consumer_task = asyncio.create_task(
            _consume_scheduler_queue(_job_queue, _orchestrator),
            name="scheduler_consumer",
        )
        logger.info(
            "Scheduler started with %d job(s)", len(_scheduler.list_jobs())
        )
    except ImportError as exc:
        logger.warning("Scheduler not available: %s", exc)

    # ── Backup manager ────────────────────────────────────────────────────
    _backup_task: asyncio.Task | None = None

    try:
        from sovereign.infra.backup_manager import BackupManager
        _backup_mgr = BackupManager()
        _backup_task = asyncio.create_task(
            _backup_mgr.run_loop(interval_hours=24, stop_event=_stop_event),
            name="backup_loop",
        )
        logger.info("BackupManager started (interval=24h)")
    except ImportError as exc:
        logger.warning("BackupManager not available: %s", exc)

    try:
        yield
    finally:
        # Signal background tasks to stop
        if _stop_event is not None:
            _stop_event.set()
        for task in (_scheduler_task, _consumer_task, _backup_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        await _orchestrator.stop_background_tasks()
        logger.info("SOVEREIGN AI OS web server shutting down")


app = FastAPI(
    title="SOVEREIGN AI OS",
    description="Multi-agent orchestration operating system — web interface",
    version=__version__,
    lifespan=lifespan,
)


class _APIRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP sliding-window rate limiter for all /api/* endpoints.

    Limits: 120 requests / 60 seconds per client IP.
    WebSocket and page routes are excluded (they have their own guards).
    """

    _EXEMPT_PREFIXES = ("/ws", "/static", "/health")

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        path = request.url.path
        if path.startswith("/api/") and not any(path.startswith(p) for p in self._EXEMPT_PREFIXES):
            ip = request.client.host if request.client else "unknown"
            if not _api_rate_check(ip):
                return JSONResponse(
                    {"error": "Rate limit exceeded", "retry_after": int(_API_RATE_WINDOW)},
                    status_code=429,
                    headers={"Retry-After": str(int(_API_RATE_WINDOW))},
                )
        return await call_next(request)


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers (including per-request CSP nonce) to every HTTP response."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        nonce = _secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce
        response = await call_next(request)
        csp = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://cdn.tailwindcss.com https://unpkg.com "
            "https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com "
            "https://fonts.gstatic.com https://cdn.tailwindcss.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self' wss: ws:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["Content-Security-Policy"] = csp
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


# ── CORS ──────────────────────────────────────────────────────────────────
_env = os.environ.get("SOVEREIGN_ENV", "")
_raw_origins = os.environ.get("SOVEREIGN_ALLOWED_ORIGINS", "")

if _raw_origins:
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
elif _env == "production":
    _allowed_origins = []  # production MUST set SOVEREIGN_ALLOWED_ORIGINS
    logging.getLogger(__name__).warning(
        "SOVEREIGN_ALLOWED_ORIGINS not set in production — CORS disabled"
    )
else:
    _allowed_origins = ["http://localhost:8080", "http://127.0.0.1:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Signature-256", "X-Webhook-Timestamp"],
)
app.add_middleware(_SecurityHeadersMiddleware)
app.add_middleware(_APIRateLimitMiddleware)

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
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        return JSONResponse({"error": "Too many login attempts"}, status_code=429)
    body = await request.json()
    password = body.get("password", "")
    expected = os.environ.get("SOVEREIGN_PASSWORD", "")
    if not expected:
        logger.warning(
            "SOVEREIGN_PASSWORD is not set — authentication is disabled. "
            "Set SOVEREIGN_PASSWORD in your .env before exposing this service."
        )
        return JSONResponse({"error": "Server not configured for authentication"}, status_code=503)
    if password != expected:
        return JSONResponse({"error": "Invalid password"}, status_code=401)
    reset_rate_limit(client_ip)
    token = create_token({"sub": "admin", "role": "admin"})
    return JSONResponse({"token": token, "expires_in": 28_800})


@app.post("/api/auth/refresh")
async def refresh_token(user: dict = Depends(require_auth)) -> JSONResponse:
    """Exchange a valid (non-expired) token for a fresh 8-hour token."""
    new_token = create_token({"sub": user.get("sub", "admin"), "role": user.get("role", "user")})
    return JSONResponse({"token": new_token, "expires_in": 28_800})


@app.get("/api/ws-ticket")
async def get_ws_ticket(_: dict = Depends(require_auth)) -> JSONResponse:
    """Issue a 30-second single-use WebSocket ticket (avoids long-lived JWT in URL logs)."""
    ticket = create_ws_ticket()
    return JSONResponse({"ticket": ticket, "expires_in": 30})


@app.post("/api/auth/logout")
async def logout(
    request: Request, user: dict = Depends(require_auth)
) -> JSONResponse:
    """Revoke the current token immediately (server-side blacklist)."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        payload = verify_token(token)
        revoke_token(payload.get("jti", ""), float(payload.get("exp", 0)))
    except Exception:
        pass
    return JSONResponse({"logged_out": True})


@app.get("/api/status")
async def public_status() -> JSONResponse:
    """Public health/status — no auth required."""
    import platform
    return JSONResponse({
        "service": "SOVEREIGN AI OS",
        "version": __version__,
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
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "index.html", {"nonce": nonce})


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Real-time bidirectional channel for agent streaming.

    Auth: short-lived ticket via ?ticket= (obtained from GET /api/ws-ticket).
    The ?token= URL parameter is no longer supported — use /api/ws-ticket instead.
    """
    ticket = ws.query_params.get("ticket", "")
    token = ws.query_params.get("token", "")
    authenticated = False

    if ticket:
        authenticated = consume_ws_ticket(ticket)
    elif token:
        await ws.close(code=4401, reason="Deprecated ?token= auth removed. Use /api/ws-ticket.")
        return

    if not authenticated:
        await ws.accept()
        await ws.send_json({"type": "error", "code": "unauthorized", "message": "Invalid or missing token"})
        await ws.close(code=4401)
        return

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
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "executive_dashboard.html", {"nonce": nonce})


@app.get("/finance", response_class=HTMLResponse)
async def finance_cockpit(request: Request) -> HTMLResponse:
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "finance_cockpit.html", {"nonce": nonce})


@app.get("/business", response_class=HTMLResponse)
async def business_wall(request: Request) -> HTMLResponse:
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "business_wall.html", {"nonce": nonce})


@app.get("/approvals", response_class=HTMLResponse)
async def approvals_center(request: Request) -> HTMLResponse:
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "approvals_center.html", {"nonce": nonce})


@app.get("/hud", response_class=HTMLResponse)
async def jarvis_hud(request: Request) -> HTMLResponse:
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "jarvis_hud.html", {"nonce": nonce})


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
async def resolve_escalation(
    event_id: str, body: ResolveRequest, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Resolve an escalation event by ID."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    success = _orchestrator.resolve_escalation(event_id, body.resolution)
    if not success:
        return JSONResponse({"error": "Event not found or already resolved"}, status_code=404)
    return JSONResponse({"resolved": event_id, "resolution": body.resolution})


@app.get("/api/agents")
async def list_agents(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return count and summary of registered agents."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    registry = _orchestrator._agent_registry
    agents = registry.list_agents()
    return JSONResponse({"count": registry.count(), "agents": agents})


@app.get("/api/metrics")
async def metrics(_: dict = Depends(require_auth)) -> JSONResponse:
    """Live session experiment metrics."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    return JSONResponse(_orchestrator.get_experiment_metrics("live_sessions"))


# ---------------------------------------------------------------------------
# REST API — Voice (STT + TTS)
# ---------------------------------------------------------------------------

@app.post("/api/voice")
async def voice_transcribe(request: Request, _: dict = Depends(require_auth)) -> JSONResponse:
    """Receive audio bytes (multipart or raw body), transcribe via Whisper, return text."""
    content_type = request.headers.get("content-type", "")
    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            audio_file = form.get("audio") or form.get("file")
            if audio_file is None:
                return JSONResponse({"error": "No audio field in form"}, status_code=400)
            audio_bytes = await audio_file.read()  # type: ignore[union-attr]
            mime = audio_file.content_type or "audio/wav"  # type: ignore[union-attr]
        else:
            audio_bytes = await request.body()
            mime = content_type or "audio/wav"
        recogniser = _get_recogniser()
        cmd = await recogniser.transcribe_bytes(audio_bytes, mime)
        return JSONResponse({"text": cmd.text, "confidence": cmd.confidence, "source": cmd.source})
    except Exception as exc:
        logger.warning("voice_transcribe error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/tts")
async def tts_synthesize(payload: dict, _: dict = Depends(require_auth)) -> Response:
    """Convert text to speech, return audio/mpeg bytes."""
    text = str(payload.get("text", "")).strip()
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)
    tts = _get_tts()
    if not tts.available:
        return JSONResponse({"error": "TTS not configured"}, status_code=503)
    try:
        voice = str(payload.get("voice", "onyx"))
        audio_bytes = await tts.speak(text, voice=voice)
        if not audio_bytes:
            return JSONResponse({"error": "TTS produced no output"}, status_code=500)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as exc:
        logger.warning("tts_synthesize error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/voice/status")
async def voice_status(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return voice subsystem status."""
    tts = _get_tts()
    recogniser = _get_recogniser()
    stt_available = bool(recogniser._api_key or recogniser._pyaudio_available)
    return JSONResponse({
        "tts_backend": tts.backend,
        "tts_available": tts.available,
        "stt_available": stt_available,
    })


# ---------------------------------------------------------------------------
# REST API — Finance (V2)
# ---------------------------------------------------------------------------

@app.get("/api/finance/summary")
async def finance_summary(_: dict = Depends(require_auth)) -> JSONResponse:
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
async def finance_transactions(
    limit: int = 50, date_from: str = "", date_to: str = "", category: str = "",
    _: dict = Depends(require_auth),
) -> JSONResponse:
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
async def finance_portfolio(_: dict = Depends(require_auth)) -> JSONResponse:
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
async def finance_cashflow(months: int = 12, _: dict = Depends(require_auth)) -> JSONResponse:
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
async def finance_import_csv(body: ImportCSVRequest, _: dict = Depends(require_auth)) -> JSONResponse:
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
async def list_projects(status: str = "", _: dict = Depends(require_auth)) -> JSONResponse:
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
async def create_project(body: CreateProjectRequest, _: dict = Depends(require_auth)) -> JSONResponse:
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
async def update_project(
    project_id: str, body: UpdateProjectRequest, _: dict = Depends(require_auth)
) -> JSONResponse:
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
async def add_task(project_id: str, body: AddTaskRequest, _: dict = Depends(require_auth)) -> JSONResponse:
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
async def complete_task(project_id: str, task_id: str, _: dict = Depends(require_auth)) -> JSONResponse:
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
async def list_goals(_: dict = Depends(require_auth)) -> JSONResponse:
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
async def add_goal(body: AddGoalRequest, _: dict = Depends(require_auth)) -> JSONResponse:
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
async def update_goal_progress(
    goal_id: str, body: UpdateProgressRequest, _: dict = Depends(require_auth)
) -> JSONResponse:
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
async def list_suggestions(_: dict = Depends(require_auth)) -> JSONResponse:
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
async def list_integrations(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return status of all integration connectors."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        return JSONResponse({"integrations": _orchestrator.integration_manager.list_all()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/connectors")
async def list_connectors(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return describe() dict for every connector registered in the SyncEngine."""
    try:
        from sovereign.integrations.connectors.sync_engine import get_sync_engine
        engine = get_sync_engine()
        return JSONResponse({"connectors": engine.list_connectors()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Labs
# ---------------------------------------------------------------------------

@app.get("/api/labs")
async def list_labs(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return status summary for all 21 experimental labs."""
    import importlib
    import pathlib as _pl
    labs_info = []
    for f in sorted(_pl.Path("sovereign/labs").glob("*.py")):
        if f.name in ("__init__.py", "labs_framework.py"):
            continue
        try:
            mod = importlib.import_module(f"sovereign.labs.{f.stem}")
            for name in dir(mod):
                obj = getattr(mod, name)
                if (
                    isinstance(obj, type)
                    and hasattr(obj, "lab_id")
                    and obj.lab_id not in ("base", "")
                ):
                    data_path = _pl.Path(f"data/labs/{obj.lab_id}_experiments.json")
                    instance = obj(data_path=str(data_path))
                    db = instance.dashboard()
                    labs_info.append({
                        "lab_id": obj.lab_id,
                        "lab_name": obj.lab_name,
                        "description": obj.description,
                        "agents": obj.agents,
                        "model": obj.model,
                        "templates": len(getattr(obj, "experiment_templates", [])),
                        "experiments": db,
                    })
        except Exception:
            pass
    return JSONResponse({"labs": labs_info, "total": len(labs_info)})


@app.get("/api/labs/{lab_id}/experiments")
async def lab_experiments(lab_id: str, _: dict = Depends(require_auth)) -> JSONResponse:
    """Return all experiments for a specific lab."""
    import importlib
    import pathlib as _pl
    for f in _pl.Path("sovereign/labs").glob("*.py"):
        if f.name in ("__init__.py", "labs_framework.py"):
            continue
        try:
            mod = importlib.import_module(f"sovereign.labs.{f.stem}")
            for name in dir(mod):
                obj = getattr(mod, name)
                if isinstance(obj, type) and hasattr(obj, "lab_id") and obj.lab_id == lab_id:
                    data_path = _pl.Path(f"data/labs/{lab_id}_experiments.json")
                    instance = obj(data_path=str(data_path))
                    exps = [
                        {
                            "experiment_id": e.experiment_id,
                            "name": e.name,
                            "status": e.status.value,
                            "hypothesis": {
                                "statement": e.hypothesis.statement,
                                "metric": e.hypothesis.metric,
                                "threshold": e.hypothesis.success_threshold,
                            },
                            "tags": e.tags,
                            "created_at": e.created_at,
                            "started_at": e.started_at,
                        }
                        for e in instance.list_experiments()
                    ]
                    return JSONResponse({"lab_id": lab_id, "experiments": exps})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse({"error": f"Lab '{lab_id}' not found"}, status_code=404)


# ---------------------------------------------------------------------------
# REST API — Expansion (capability gaps + model performance)
# ---------------------------------------------------------------------------

@app.get("/expansion", response_class=HTMLResponse)
async def expansion_dashboard(request: Request) -> HTMLResponse:
    """Serve the Expansion Dashboard."""
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "expansion_dashboard.html", {"nonce": nonce})


@app.get("/api/expansion/gaps")
async def expansion_gaps(_: dict = Depends(require_auth)) -> JSONResponse:
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
async def expansion_agents(_: dict = Depends(require_auth)) -> JSONResponse:
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
async def expansion_model_perf(_: dict = Depends(require_auth)) -> JSONResponse:
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
# REST API — Memory domains
# ---------------------------------------------------------------------------

@app.get("/api/memory/search")
async def memory_semantic_search(
    q: str,
    domain: str = "",
    top_k: int = 5,
    _: dict = Depends(require_auth),
) -> JSONResponse:
    """Semantic (TF-IDF cosine) search across all or a specific memory domain."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    if not q.strip():
        return JSONResponse({"error": "Query parameter 'q' is required"}, status_code=400)
    try:
        results = await _orchestrator._memory.semantic_search(
            query=q,
            domain=domain or None,
            top_k=min(top_k, 20),
        )
        return JSONResponse({"query": q, "results": results, "count": len(results)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/memory/{domain}")
async def memory_domain(domain: str, _: dict = Depends(require_auth)) -> JSONResponse:
    """Read a memory domain snapshot."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        data = await _orchestrator._memory.read(domain)
        return JSONResponse({"domain": domain, "data": data})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Operating mode
# ---------------------------------------------------------------------------

@app.get("/api/mode")
async def get_mode(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return the current operating mode."""
    if _orchestrator is None:
        return JSONResponse({"mode": "command"})
    return JSONResponse({"mode": _orchestrator.current_mode})


class SetModeRequest(BaseModel):
    mode: str


@app.post("/api/mode")
async def set_mode(body: SetModeRequest, _: dict = Depends(require_auth)) -> JSONResponse:
    """Switch operating mode."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    ok = _orchestrator.set_mode(body.mode)
    if not ok:
        return JSONResponse({"error": f"Unknown mode: {body.mode!r}"}, status_code=400)
    return JSONResponse({"mode": _orchestrator.current_mode})


# ---------------------------------------------------------------------------
# REST API — Connected Entity Provisioning
# ---------------------------------------------------------------------------

@app.get("/entities", response_class=HTMLResponse)
async def entities_panel(request: Request) -> HTMLResponse:
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "entities_panel.html", {"nonce": nonce})


@app.get("/settings", response_class=HTMLResponse)
async def settings_panel(request: Request) -> HTMLResponse:
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "settings_panel.html", {"nonce": nonce})


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request) -> HTMLResponse:
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "admin_panel.html", {"nonce": nonce})


class ProvisionRequest(BaseModel):
    name: str
    category: str = "account"
    connector_config: dict | None = None
    agent_bindings: list[str] = []
    files: list[str] = []
    ui_panel: str = "dashboard"
    sync_interval_s: float = 3600.0
    metadata: dict = {}


@app.get("/api/entities")
async def list_entities(category: str = "", _: dict = Depends(require_auth)) -> JSONResponse:
    """List all provisioned entities."""
    if _orchestrator is None:
        return JSONResponse({"entities": []})
    try:
        return JSONResponse({"entities": _orchestrator.entity_provisioner.list_entities(category)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/entities")
async def provision_entity(body: ProvisionRequest, _: dict = Depends(require_auth)) -> JSONResponse:
    """Provision a new connected entity."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        entity = _orchestrator.entity_provisioner.provision(
            name=body.name, category=body.category,
            connector_config=body.connector_config,
            agent_bindings=body.agent_bindings, files=body.files,
            ui_panel=body.ui_panel, sync_interval_s=body.sync_interval_s,
            metadata=body.metadata,
        )
        from dataclasses import asdict
        return JSONResponse(asdict(entity), status_code=201)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/entities/{entity_id}")
async def get_entity(entity_id: str, _: dict = Depends(require_auth)) -> JSONResponse:
    """Get a single entity summary."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        summary = _orchestrator.entity_provisioner.get_entity_summary(entity_id)
        if summary is None:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        return JSONResponse(summary)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/entities/{entity_id}/sync")
async def sync_entity(entity_id: str, _: dict = Depends(require_auth)) -> JSONResponse:
    """Trigger a manual sync for an entity."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        result = _orchestrator.entity_provisioner.sync(entity_id)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.patch("/api/entities/{entity_id}")
async def update_entity(entity_id: str, body: dict, _: dict = Depends(require_auth)) -> JSONResponse:
    """Update entity status or metadata."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        reg = _orchestrator.entity_provisioner._registry
        entity = reg.get(entity_id)
        if entity is None:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        if "status" in body:
            entity.status = body["status"]
        if "metadata" in body:
            entity.metadata.update(body["metadata"])
        if "sync_interval_s" in body:
            entity.sync_interval_s = float(body["sync_interval_s"])
        reg._save()
        return JSONResponse({"updated": entity_id, "status": entity.status})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Provider health
# ---------------------------------------------------------------------------

@app.get("/api/providers")
async def list_providers(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return health status for all model providers (Anthropic, OpenAI, Qwen, etc.)."""
    if _orchestrator is None:
        return JSONResponse({"providers": {}})
    try:
        report = _orchestrator._model_router.provider_health_report()
        return JSONResponse({"providers": report})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — User settings
# ---------------------------------------------------------------------------

@app.get("/api/settings")
async def get_settings(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return all user settings."""
    from sovereign.api.user_settings import get_settings_store
    return JSONResponse(get_settings_store().get_all())


@app.get("/api/settings/{section}")
async def get_settings_section(section: str, _: dict = Depends(require_auth)) -> JSONResponse:
    """Return a single settings section."""
    from sovereign.api.user_settings import get_settings_store
    try:
        return JSONResponse(get_settings_store().get_section(section))
    except KeyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)


class SettingsUpdateRequest(BaseModel):
    data: dict


@app.patch("/api/settings/{section}")
async def update_settings_section(
    section: str, body: SettingsUpdateRequest, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Update a settings section."""
    from sovereign.api.user_settings import get_settings_store
    try:
        updated = get_settings_store().update_section(section, body.data)
        return JSONResponse(updated)
    except KeyError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/settings/reset")
async def reset_settings(_: dict = Depends(require_auth)) -> JSONResponse:
    """Reset all settings to defaults."""
    from sovereign.api.user_settings import get_settings_store
    return JSONResponse(get_settings_store().reset())


# ---------------------------------------------------------------------------
# REST API — Agent Feedback (thumbs up / down → prompt scoring)
# ---------------------------------------------------------------------------

@app.post("/api/feedback")
async def submit_feedback(
    payload: dict, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Record user feedback (thumbs up/down) for an agent response.

    Expected payload keys:
        agent_id   — agent that produced the response.
        session_id — current session identifier.
        task_id    — message / task identifier (may be empty string).
        rating     — +1 (thumbs up) or -1 (thumbs down).
        comment    — optional free-text comment.
    """
    try:
        agent_id   = str(payload.get("agent_id",   "unknown"))
        session_id = str(payload.get("session_id", ""))
        task_id    = str(payload.get("task_id",    ""))
        rating     = int(payload.get("rating",     0))
        comment    = str(payload.get("comment",    ""))
        if rating not in (1, -1):
            return JSONResponse({"error": "rating must be +1 or -1"}, status_code=400)
        registry = _get_feedback_registry()
        registry.record(
            agent_id=agent_id,
            session_id=session_id,
            task_id=task_id,
            rating=rating,
            comment=comment,
        )
        score = registry.agent_score(agent_id)
        return JSONResponse({"ok": True, "agent_score": score})
    except Exception as exc:
        logger.warning("submit_feedback error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/feedback/summary")
async def feedback_summary(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return aggregate feedback summary — used by the dashboard."""
    try:
        return JSONResponse(_get_feedback_registry().summary())
    except Exception as exc:
        logger.warning("feedback_summary error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Session history (SQLite-backed)
# ---------------------------------------------------------------------------

@app.get("/api/sessions")
async def list_sessions(request: Request) -> JSONResponse:
    """List recent chat sessions."""
    require_auth(request)
    try:
        from sovereign.persistence.session_store import SessionStore
        return JSONResponse({"sessions": SessionStore().list_sessions()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str, request: Request) -> JSONResponse:
    """Return the message history for a specific session."""
    require_auth(request)
    try:
        from sovereign.persistence.session_store import SessionStore
        return JSONResponse({
            "session_id": session_id,
            "messages": SessionStore().get_history(session_id),
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Module admin
# ---------------------------------------------------------------------------

@app.get("/api/admin/modules")
async def list_modules(_: dict = Depends(require_auth)) -> JSONResponse:
    """List all registered tools/agents as 'modules' with status info."""
    if _orchestrator is None:
        return JSONResponse({"modules": []})
    try:
        agents = _orchestrator._agent_registry.list_agents()
        tools  = _orchestrator._tool_registry.list_tools() if hasattr(_orchestrator._tool_registry, "list_tools") else []
        modules = []
        for a in agents:
            if isinstance(a, dict):
                modules.append({
                    "id":     a.get("agent_id", ""),
                    "name":   a.get("agent_id", ""),
                    "type":   "agent",
                    "status": "active",
                    "model":  a.get("model", ""),
                    "stage":  a.get("stage", "production"),
                })
        for t in tools:
            tid = t if isinstance(t, str) else t.get("tool_id", "")
            modules.append({"id": tid, "name": tid, "type": "tool", "status": "active", "stage": "production"})
        return JSONResponse({"modules": modules, "count": len(modules)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/admin/modules/{module_id}")
async def get_module(module_id: str, _: dict = Depends(require_auth)) -> JSONResponse:
    """Get details for a specific agent module."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        agent = _orchestrator._agent_registry.get(module_id)
        if agent is None:
            return JSONResponse({"error": f"Module {module_id!r} not found"}, status_code=404)
        return JSONResponse({
            "id":      module_id,
            "type":    "agent",
            "status":  "active",
            "details": str(agent),
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/admin/provider-health")
async def admin_provider_health(_: dict = Depends(require_auth)) -> JSONResponse:
    """Detailed provider health with circuit-breaker state."""
    if _orchestrator is None:
        return JSONResponse({"providers": {}})
    try:
        report = _orchestrator._model_router.provider_health_report()
        return JSONResponse({"providers": report, "healthy": _orchestrator._model_router.health.healthy_providers()})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Life Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard")
async def life_dashboard(_: dict = Depends(require_auth)) -> JSONResponse:
    """Aggregate life data from all memory domains and return a unified dashboard snapshot."""
    import datetime as _dt

    result: dict = {
        "finance": {
            "available_cash": 0.0,
            "monthly_income": 0.0,
            "monthly_expenses": 0.0,
            "net_worth": 0.0,
            "goals_2026": [],
            "budget_status": "on_track",
        },
        "projects": {
            "active": [],
            "urgent_tasks": [],
        },
        "health": {
            "training_this_week": 0,
            "weight_kg": 0.0,
            "fitness_level": "",
            "active_routines": [],
        },
        "learning": {
            "in_progress": [],
            "expert_skills": [],
        },
        "relationships": {
            "pending_follow_ups": 0,
            "dormant_contacts": 0,
        },
        "decisions": {
            "open": [],
            "pending_review": [],
        },
        "weekly_summary": {
            "period": _dt.date.today().strftime("%G-W%V"),
            "diary_avg_mood": 5.0,
            "decisions_made": 0,
            "content_published": 0,
        },
    }

    # ── Finance ──────────────────────────────────────────────────────────
    try:
        from sovereign.memory.domains.financial import FinancialMemoryStore
        fin = FinancialMemoryStore()
        snap = fin.get_snapshot()
        result["finance"]["available_cash"]  = float(snap.get("available_cash", snap.get("cash", 0.0)))
        result["finance"]["monthly_income"]  = float(snap.get("monthly_income", 0.0))
        result["finance"]["monthly_expenses"]= float(snap.get("monthly_expenses", 0.0))
        result["finance"]["net_worth"]       = float(snap.get("net_worth", 0.0))
        result["finance"]["budget_status"]   = snap.get("budget_status", "on_track")
    except Exception as exc:
        logger.debug("dashboard finance error: %s", exc)

    # ── Goals 2026 (from identity primary_goals) ─────────────────────────
    try:
        from sovereign.memory.domains.identity import IdentityMemoryStore
        ident = IdentityMemoryStore()
        identity_rec = ident.get_identity()
        result["finance"]["goals_2026"] = list(identity_rec.primary_goals or [])
    except Exception as exc:
        logger.debug("dashboard identity error: %s", exc)

    # ── Projects ─────────────────────────────────────────────────────────
    try:
        from sovereign.memory.domains.project import ProjectMemoryStore
        proj_store = ProjectMemoryStore()
        active_projects = proj_store.get_projects(status="active")
        result["projects"]["active"] = [
            {
                "id":       p.get("project_id", ""),
                "name":     p.get("name", ""),
                "progress": p.get("progress", 0),
                "deadline": p.get("deadline", ""),
                "status":   p.get("status", ""),
            }
            for p in active_projects
        ]
        # Collect urgent tasks (priority == 1 or status == blocked) across all projects
        urgent: list[dict] = []
        for p in active_projects:
            for task in p.get("tasks", []):
                if task.get("priority", 2) == 1 or task.get("status") == "blocked":
                    urgent.append({
                        "project":  p.get("name", ""),
                        "task":     task.get("title", ""),
                        "status":   task.get("status", ""),
                        "due_date": task.get("due_date", ""),
                    })
        result["projects"]["urgent_tasks"] = urgent[:10]
    except Exception as exc:
        logger.debug("dashboard projects error: %s", exc)

    # ── Health ───────────────────────────────────────────────────────────
    try:
        from sovereign.memory.domains.health_routine import HealthRoutineMemoryStore
        health_store = HealthRoutineMemoryStore()
        profile = health_store.get_profile()
        # Count training sessions logged this ISO week
        import datetime as _dt2
        week_start = (_dt2.date.today() - _dt2.timedelta(days=_dt2.date.today().weekday())).isoformat()
        # Count generic "training" entries this week
        all_recent = health_store.recent_metrics(n=50)
        training_this_week = sum(
            1 for m in all_recent
            if m.recorded_at[:10] >= week_start and m.metric_type in ("steps", "training", "workout")
        )
        weight_metrics = health_store.recent_metrics(metric_type="weight", n=1)
        result["health"]["training_this_week"] = training_this_week
        result["health"]["weight_kg"] = float(weight_metrics[0].value) if weight_metrics else float(profile.weight_kg)
        result["health"]["fitness_level"] = profile.fitness_level
        result["health"]["active_routines"] = [
            {"id": r.routine_id, "name": r.name, "frequency": r.frequency}
            for r in health_store.active_routines()
        ]
    except Exception as exc:
        logger.debug("dashboard health error: %s", exc)

    # ── Learning ─────────────────────────────────────────────────────────
    try:
        from sovereign.memory.domains.learning import LearningMemoryStore
        learn_store = LearningMemoryStore()
        in_progress = learn_store.by_status("in_progress")
        all_skills = learn_store.all_skills()
        result["learning"]["in_progress"] = [
            {"id": i.item_id, "title": i.title, "progress_pct": i.progress_pct, "type": i.item_type}
            for i in in_progress
        ]
        result["learning"]["expert_skills"] = [
            s.skill_name for s in all_skills if s.level in ("advanced", "expert")
        ]
    except Exception as exc:
        logger.debug("dashboard learning error: %s", exc)

    # ── Relationships ────────────────────────────────────────────────────
    try:
        from sovereign.memory.domains.relationship import RelationshipMemoryStore
        rel_store = RelationshipMemoryStore()
        contacts = list(rel_store._data.get("contacts", {}).values())
        interactions = list(rel_store._data.get("interactions", []))
        # Pending follow-ups: interactions with follow_up_needed=True and not yet resolved
        pending_follow_ups = sum(1 for i in interactions if i.get("follow_up_needed"))
        # Dormant contacts: last_contact older than 90 days or never contacted
        import datetime as _dt3
        cutoff = (_dt3.date.today() - _dt3.timedelta(days=90)).isoformat()
        dormant = sum(
            1 for c in contacts
            if not c.get("last_contact") or c.get("last_contact", "") < cutoff
        )
        result["relationships"]["pending_follow_ups"] = pending_follow_ups
        result["relationships"]["dormant_contacts"] = dormant
    except Exception as exc:
        logger.debug("dashboard relationships error: %s", exc)

    # ── Decisions ────────────────────────────────────────────────────────
    try:
        from sovereign.memory.domains.decision import DecisionMemoryStore
        dec_store = DecisionMemoryStore()
        open_decisions = dec_store.by_status("open")
        decided = dec_store.by_status("decided")
        # Decisions due for review
        import datetime as _dt4
        today_str = _dt4.date.today().isoformat()
        pending_review = [d for d in decided if d.review_at and d.review_at[:10] <= today_str]
        result["decisions"]["open"] = [
            {"id": d.decision_id, "title": d.title, "domain": d.domain, "confidence": d.confidence}
            for d in open_decisions[:10]
        ]
        result["decisions"]["pending_review"] = [
            {"id": d.decision_id, "title": d.title, "review_at": d.review_at}
            for d in pending_review[:10]
        ]
        result["weekly_summary"]["decisions_made"] = len(decided)
    except Exception as exc:
        logger.debug("dashboard decisions error: %s", exc)

    # ── Weekly summary (diary mood) ───────────────────────────────────────
    try:
        from sovereign.memory.domains.diary import DiaryMemoryStore
        diary_store = DiaryMemoryStore()
        recent_entries = diary_store.recent(n=7)
        if recent_entries:
            avg_mood = sum(e.mood_score for e in recent_entries) / len(recent_entries)
            result["weekly_summary"]["diary_avg_mood"] = round(avg_mood, 1)
    except Exception as exc:
        logger.debug("dashboard diary error: %s", exc)

    # ── Content published this week (from content domain) ────────────────
    try:
        from sovereign.memory.domains.content import ContentMemoryStore
        content_store = ContentMemoryStore()
        import datetime as _dt5
        week_start_str = (_dt5.date.today() - _dt5.timedelta(days=_dt5.date.today().weekday())).isoformat()
        all_content = list(content_store._data.get("items", {}).values()) if hasattr(content_store, "_data") else []
        published = sum(
            1 for c in all_content
            if c.get("status") == "published" and c.get("published_at", "")[:10] >= week_start_str
        )
        result["weekly_summary"]["content_published"] = published
    except Exception as exc:
        logger.debug("dashboard content error: %s", exc)

    return JSONResponse(result)


@app.post("/api/dashboard/report")
async def dashboard_report(_: dict = Depends(require_auth)) -> JSONResponse:
    """Generate and send weekly report via Telegram."""
    try:
        from sovereign.reporting.weekly_report import run_weekly_report
        report_text = await run_weekly_report()
        return JSONResponse({"sent": True, "length": len(report_text)})
    except Exception as exc:
        return JSONResponse({"sent": False, "error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Morning brief
# ---------------------------------------------------------------------------

@app.get("/api/brief")
async def morning_brief(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return today's morning briefing as structured JSON."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        import pathlib
        data_dir = pathlib.Path("data")
        result: dict = {"generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z"}

        # Urgent next actions
        try:
            from sovereign.memory.domains.next_action import NextActionStore
            na = NextActionStore(data_dir / "memory" / "next_action.json")
            result["urgent_actions"] = [
                {"id": a.action_id, "title": a.title, "priority": a.priority}
                for a in na.urgent()[:5]
            ]
            result["overdue_actions"] = len(na.overdue())
        except Exception:
            result["urgent_actions"] = []
            result["overdue_actions"] = 0

        # Open decisions
        try:
            from sovereign.memory.domains.decision import DecisionMemoryStore
            dec = DecisionMemoryStore(data_dir / "memory" / "decision.json")
            open_d = dec.by_status("open")
            result["open_decisions"] = [
                {"id": d.decision_id, "title": d.title}
                for d in open_d[:5]
            ]
        except Exception:
            result["open_decisions"] = []

        # Diary mood (7-day avg)
        try:
            from sovereign.memory.domains.diary import DiaryMemoryStore
            diary = DiaryMemoryStore(data_dir / "memory" / "diary.json")
            result["mood_avg_7d"] = round(diary.average_mood(7), 1)
        except Exception:
            result["mood_avg_7d"] = None

        # Active goals
        result["goals"] = _orchestrator.goal_monitor.summary()

        # Budget
        try:
            budget = _orchestrator.get_budget_summary()
            result["budget"] = {
                "daily_tokens": budget["daily"].get("tokens", 0),
                "daily_cost_usd": budget["daily"].get("cost_usd", 0),
                "daily_limit_usd": budget["daily"].get("limit_usd", 0),
            }
        except Exception:
            result["budget"] = {}

        # Pending approvals
        result["pending_approvals"] = len(_orchestrator.get_pending_escalations())

        # Personal constitution mission
        try:
            from sovereign.memory.domains.personal_constitution import PersonalConstitutionStore
            pcs = PersonalConstitutionStore(data_dir / "memory" / "personal_constitution.json")
            con = pcs.get_constitution()
            result["mission"] = con.personal_mission
        except Exception:
            result["mission"] = ""

        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Daily digest
# ---------------------------------------------------------------------------

@app.get("/api/digest")
async def daily_digest(_: dict = Depends(require_auth)) -> JSONResponse:
    """Generate and return the daily digest report as text."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.proactive.daily_digest import DailyDigest
        digest = DailyDigest(_orchestrator)
        report = await digest.generate()
        return JSONResponse({
            "text": report.text,
            "generated_at": report.generated_at,
            "length": len(report.text),
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/digest/send")
async def send_daily_digest(_: dict = Depends(require_auth)) -> JSONResponse:
    """Generate digest and deliver via Telegram."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        from sovereign.proactive.daily_digest import DailyDigest
        digest = DailyDigest(_orchestrator)
        report = await digest.generate()
        tg = getattr(_orchestrator, "_telegram_bot", None)
        sent = False
        if tg is not None:
            await tg.send_alert(report.to_telegram(), level="info")
            sent = True
        return JSONResponse({"sent": sent, "length": len(report.text)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Process watchdog
# ---------------------------------------------------------------------------

@app.get("/api/watchdog")
async def watchdog_status(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return the process watchdog health summary."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        return JSONResponse(_orchestrator.process_watchdog.health_summary())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Inbound webhooks
# ---------------------------------------------------------------------------

@app.post("/api/webhooks/{source}/{event_type}")
async def inbound_webhook(
    source: str,
    event_type: str,
    request: Request,
) -> JSONResponse:
    """Receive an inbound webhook, validate HMAC signature, dispatch to handlers."""
    import hashlib
    import hmac
    import json
    import time as _time

    raw_body = await request.body()

    # Payload size limit: 64 KB
    if len(raw_body) > 65_536:
        return JSONResponse({"error": "Payload too large (max 64 KB)"}, status_code=413)

    # HMAC-SHA256 validation — enforced when SOVEREIGN_WEBHOOK_SECRET is set
    webhook_secret = os.environ.get("SOVEREIGN_WEBHOOK_SECRET", "")
    if webhook_secret:
        sig_header = request.headers.get("X-Signature-256", "")
        ts_header = request.headers.get("X-Webhook-Timestamp", "")
        if not sig_header or not ts_header:
            logger.warning("Webhook %s/%s missing signature headers", source, event_type)
            return JSONResponse({"error": "Missing X-Signature-256 or X-Webhook-Timestamp"}, status_code=401)
        try:
            ts = int(ts_header)
            if abs(_time.time() - ts) > 300:
                return JSONResponse({"error": "Webhook timestamp expired (max 5 min skew)"}, status_code=403)
        except ValueError:
            return JSONResponse({"error": "Invalid X-Webhook-Timestamp"}, status_code=400)
        expected = hmac.new(
            webhook_secret.encode(),
            f"{ts_header}.{source}.{event_type}.".encode() + raw_body,
            hashlib.sha256,
        ).hexdigest()
        received = sig_header.removeprefix("sha256=")
        if not hmac.compare_digest(expected, received):
            logger.warning("Webhook %s/%s signature mismatch", source, event_type)
            return JSONResponse({"error": "Invalid webhook signature"}, status_code=401)
    else:
        logger.warning(
            "SOVEREIGN_WEBHOOK_SECRET not set — webhook %s/%s accepted without auth", source, event_type
        )

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except Exception:
        payload = {}

    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        event = await _orchestrator.webhook_router.receive(source, event_type, payload)
        return JSONResponse({
            "event_id": event.event_id,
            "source": event.source,
            "event_type": event.event_type,
            "processed": event.processed,
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/webhooks/stats")
async def webhook_stats(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return webhook processing statistics."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        stats = _orchestrator.webhook_router.stats()
        history = [
            {
                "event_id": e.event_id,
                "source": e.source,
                "event_type": e.event_type,
                "processed": e.processed,
                "received_at": e.received_at,
            }
            for e in _orchestrator.webhook_router.event_history(limit=20)
        ]
        return JSONResponse({"stats": stats, "recent": history})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.delete("/api/entities/{entity_id}")
async def deprovision_entity(entity_id: str, _: dict = Depends(require_auth)) -> JSONResponse:
    """Deprovision and delete an entity."""
    if _orchestrator is None:
        return JSONResponse({"error": "Not initialised"}, status_code=503)
    try:
        ok = _orchestrator.entity_provisioner.deprovision(entity_id)
        if not ok:
            return JSONResponse({"error": "Entity not found"}, status_code=404)
        return JSONResponse({"deprovisioned": entity_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Next Actions (GTD)
# ---------------------------------------------------------------------------

@app.get("/api/next-actions")
async def list_next_actions(
    status: str = "",
    priority: str = "",
    context: str = "",
    _: dict = Depends(require_auth),
) -> JSONResponse:
    """List next actions with optional status/priority/context filters."""
    try:
        import pathlib
        from sovereign.memory.domains.next_action import NextActionStore
        store = NextActionStore(pathlib.Path("data/memory/next_action.json"))
        all_actions = list(store._data.get("actions", {}).values())

        if status:
            all_actions = [a for a in all_actions if a.get("status") == status]
        if priority:
            all_actions = [a for a in all_actions if a.get("priority") == priority]
        if context:
            all_actions = [a for a in all_actions if a.get("context") == context]

        urgent = [a["action_id"] for a in all_actions
                  if a.get("priority") in ("high", "critical") and a.get("status") == "pending"]
        overdue_ids = [a["action_id"] for a in store.overdue()]

        return JSONResponse({
            "total": len(all_actions),
            "urgent_count": len(store.urgent()),
            "overdue_count": len(store.overdue()),
            "actions": all_actions[:50],
            "urgent_ids": urgent,
            "overdue_ids": overdue_ids,
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class NextActionBody(BaseModel):
    title: str
    project_id: str = ""
    context: str = "@anywhere"
    energy_required: str = "medium"
    time_estimate_min: int = 30
    priority: str = "medium"
    due_date: str = ""
    notes: str = ""
    tags: list[str] = []


@app.post("/api/next-actions")
async def create_next_action(
    body: NextActionBody, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Create a new next action."""
    try:
        import pathlib
        import uuid
        from sovereign.memory.domains.next_action import NextAction, NextActionStore
        store = NextActionStore(pathlib.Path("data/memory/next_action.json"))
        action = NextAction(
            action_id=str(uuid.uuid4())[:12],
            title=body.title,
            project_id=body.project_id,
            context=body.context,
            energy_required=body.energy_required,
            time_estimate_min=body.time_estimate_min,
            priority=body.priority,
            due_date=body.due_date,
            notes=body.notes,
            tags=body.tags,
        )
        store.add_action(action)
        return JSONResponse(action.to_dict(), status_code=201)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.patch("/api/next-actions/{action_id}/complete")
async def complete_next_action(
    action_id: str, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Mark a next action as completed."""
    try:
        import pathlib
        from sovereign.memory.domains.next_action import NextActionStore
        store = NextActionStore(pathlib.Path("data/memory/next_action.json"))
        store.complete_action(action_id)
        return JSONResponse({"completed": action_id})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Personal Constitution
# ---------------------------------------------------------------------------

@app.get("/api/constitution")
async def get_constitution(_: dict = Depends(require_auth)) -> JSONResponse:
    """Return the personal constitution and active red flags."""
    try:
        import pathlib
        from dataclasses import asdict
        from sovereign.memory.domains.personal_constitution import PersonalConstitutionStore
        store = PersonalConstitutionStore(pathlib.Path("data/memory/personal_constitution.json"))
        con = store.get_constitution()
        flags = store.red_flags()
        return JSONResponse({
            "constitution": asdict(con),
            "red_flags": [
                {"flag_id": f.flag_id, "title": f.title, "severity": f.severity,
                 "category": f.category, "active": f.active}
                for f in flags
            ],
            "critical_count": len(store.red_flags_by_severity("critical")),
            "high_count": len(store.red_flags_by_severity("high")),
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class ConstitutionBody(BaseModel):
    core_values: list[str] = []
    life_principles: list[str] = []
    non_negotiables: list[str] = []
    goals_2026: list[str] = []
    personal_mission: str = ""
    personal_vision: str = ""
    daily_non_negotiables: list[str] = []


@app.patch("/api/constitution")
async def update_constitution(
    body: ConstitutionBody, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Update the personal constitution."""
    try:
        import pathlib
        from sovereign.memory.domains.personal_constitution import PersonalConstitutionStore
        store = PersonalConstitutionStore(pathlib.Path("data/memory/personal_constitution.json"))
        updates = {k: v for k, v in body.model_dump().items() if v}
        store.update_constitution(**updates)
        return JSONResponse({"updated": True})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Personal Version
# ---------------------------------------------------------------------------

@app.get("/api/personal-version")
async def get_personal_version(n: int = 6, _: dict = Depends(require_auth)) -> JSONResponse:
    """Return the latest personal version snapshot and trend data."""
    try:
        import pathlib
        from dataclasses import asdict
        from sovereign.memory.domains.personal_version import PersonalVersionStore
        store = PersonalVersionStore(pathlib.Path("data/memory/personal_version.json"))
        latest = store.latest()
        history = store.history(n=n)
        trend = store.trend_net_worth()
        return JSONResponse({
            "latest": asdict(latest) if latest else None,
            "history": [asdict(v) for v in history],
            "trend_net_worth": trend,
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


class PersonalVersionBody(BaseModel):
    period: str
    version_label: str = ""
    weight_kg: float = 0.0
    net_worth: float = 0.0
    monthly_income: float = 0.0
    monthly_expenses: float = 0.0
    savings_rate_pct: float = 0.0
    overall_rating: int = 5
    month_summary: str = ""
    next_month_focus: str = ""
    achievements: list[str] = []
    lessons: list[str] = []


@app.post("/api/personal-version")
async def save_personal_version(
    body: PersonalVersionBody, _: dict = Depends(require_auth)
) -> JSONResponse:
    """Save a personal version snapshot for the given month."""
    try:
        import pathlib
        import uuid
        from sovereign.memory.domains.personal_version import PersonalVersion, PersonalVersionStore
        store = PersonalVersionStore(pathlib.Path("data/memory/personal_version.json"))
        version = PersonalVersion(
            version_id=str(uuid.uuid4())[:12],
            period=body.period,
            version_label=body.version_label,
            weight_kg=body.weight_kg,
            net_worth=body.net_worth,
            monthly_income=body.monthly_income,
            monthly_expenses=body.monthly_expenses,
            savings_rate_pct=body.savings_rate_pct,
            overall_rating=body.overall_rating,
            month_summary=body.month_summary,
            next_month_focus=body.next_month_focus,
            achievements=body.achievements,
            lessons=body.lessons,
        )
        store.save_version(version)
        return JSONResponse({"saved": version.version_id, "period": body.period}, status_code=201)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# REST API — Business Ideas
# ---------------------------------------------------------------------------

@app.get("/api/business-ideas")
async def list_business_ideas(status: str = "", _: dict = Depends(require_auth)) -> JSONResponse:
    """Return business ideas with optional status filter."""
    try:
        import pathlib
        from sovereign.memory.domains.business_idea import BusinessIdeaMemoryStore
        store = BusinessIdeaMemoryStore(pathlib.Path("data/memory/business_idea.json"))
        ideas = store.by_status(status) if status else store.top_scored(50)
        return JSONResponse({
            "total": len(store._data.get("ideas", {})),
            "ideas": [
                {"idea_id": i.idea_id, "name": i.name, "score": i.score,
                 "status": i.status, "potential_monthly_revenue": i.potential_monthly_revenue}
                for i in ideas
            ],
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# MARSEV Private Portal
# ---------------------------------------------------------------------------

@app.get("/marsev", response_class=HTMLResponse)
async def marsev_portal(request: Request) -> HTMLResponse:
    """Serve the MARSEV private portal page."""
    nonce = getattr(request.state, "csp_nonce", "")
    return templates.TemplateResponse(request, "marsev.html", {"nonce": nonce})


@app.post("/api/chat")
async def chat_endpoint(
    request: Request,
    _: dict = Depends(require_auth),
) -> JSONResponse:
    """Chat endpoint for the MARSEV portal AI interface."""
    try:
        body = await request.json()
        message = str(body.get("message", "")).strip()
        session_id = str(body.get("session_id", ""))
        if not message:
            return JSONResponse({"error": "message required"}, status_code=400)
        if _orchestrator is None:
            return JSONResponse(
                {"reply": "MARSEV orchestrator not initialised — start the server with ANTHROPIC_API_KEY set."}
            )
        result = await _orchestrator.handle_request(message)
        if hasattr(result, "result"):
            reply = str(result.result or "")
        elif isinstance(result, dict):
            reply = str(result.get("result") or result.get("reply") or result)
        else:
            reply = str(result)
        return JSONResponse({"reply": reply, "session_id": session_id})
    except Exception as exc:
        logger.warning("chat endpoint error: %s", exc)
        return JSONResponse({"reply": f"Error: {exc}"}, status_code=500)
