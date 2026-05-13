"""
WebSocket session manager for SOVEREIGN AI OS.

Bridges WebSocket JSON messages ↔ the orchestrator.

Message protocol:

  Client → Server
  ───────────────
  { "type": "chat",         "session_id": "...", "message": "...", "mode": "..." }
  { "type": "memory_fetch", "domain": "..." }
  { "type": "health_poll" }
  { "type": "cancel",       "session_id": "..." }

  Server → Client
  ───────────────
  { "type": "stream_delta",  "session_id": "...", "delta": "..." }
  { "type": "stream_done",   "session_id": "...", "status": "...", "confidence": 0.0,
                              "tokens": {...}, "mode": "...", "requires_human_review": false }
  { "type": "agent_status",  "session_id": "...", "agent": "...", "phase": "..." }
  { "type": "tool_call",     "session_id": "...", "tool": "...", "input": {...} }
  { "type": "health",        "overall": "...", "checks": {...}, "metrics": {...}, "alerts": [...] }
  { "type": "memory_data",   "domain": "...", "keys": [...], "records": {...} }
  { "type": "error",         "session_id": "...", "code": "...", "message": "..." }
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

try:
    from sovereign.persistence.session_store import SessionStore as _SessionStore
except Exception:  # pragma: no cover
    _SessionStore = None  # type: ignore[assignment,misc]

_MAX_MSG_SIZE = 32_768  # 32 KiB


class _RateLimiter:
    """Token-bucket rate limiter: max_msgs messages per window_s seconds."""

    def __init__(self, max_msgs: int = 30, window_s: float = 10.0) -> None:
        self._max = max_msgs
        self._window = window_s
        self._timestamps: deque = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        while self._timestamps and self._timestamps[0] < now - self._window:
            self._timestamps.popleft()
        if len(self._timestamps) >= self._max:
            return False
        self._timestamps.append(now)
        return True


class WebSocketSessionManager:
    """
    Manages all WebSocket client connections and bridges them to the orchestrator.

    One instance is shared across all connections (created in server lifespan).
    Per-connection state is kept on the stack / in local variables within `handle()`.
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orch = orchestrator
        # Map session_id → asyncio.Task for in-flight chat tasks (for cancellation)
        self._active_tasks: dict[str, asyncio.Task] = {}
        # SQLite session persistence (graceful fallback if unavailable)
        self._sessions: Any = _SessionStore() if _SessionStore is not None else None

    # ------------------------------------------------------------------
    # Main entry — one coroutine per WebSocket connection
    # ------------------------------------------------------------------

    async def handle(self, ws: WebSocket) -> None:
        """
        Handle a single WebSocket connection until it disconnects.
        Pushes initial health data on connect; sends periodic heartbeat pings.
        """
        # Push health immediately on connect
        await self._send(ws, {"type": "health", **self._orch.health()})

        # Start a heartbeat task: ping every 30 s
        heartbeat_task = asyncio.create_task(self._heartbeat(ws))
        limiter = _RateLimiter(max_msgs=30, window_s=10.0)

        try:
            async for raw in ws.iter_text():
                # Message size guard
                if len(raw) > _MAX_MSG_SIZE:
                    await self._send(ws, {"type": "error", "message": "Message too large"})
                    continue
                if raw == "__ping__":
                    await self._send(ws, {"type": "pong"})
                    continue
                # Rate limit check
                if not limiter.allow():
                    await self._send(ws, {"type": "error", "message": "Rate limit exceeded — slow down"})
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send(ws, {
                        "type": "error",
                        "code": "parse_error",
                        "message": "Invalid JSON",
                    })
                    continue
                await self._dispatch(ws, msg)
        finally:
            heartbeat_task.cancel()

    async def _heartbeat(self, ws: WebSocket) -> None:
        """Send a heartbeat ping every 30 s to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(30)
                await self._send(ws, {"type": "ping", "ts": asyncio.get_event_loop().time()})
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Message dispatcher
    # ------------------------------------------------------------------

    async def _dispatch(self, ws: WebSocket, msg: dict) -> None:
        """Route an incoming message to the appropriate handler."""
        mtype = msg.get("type")

        if mtype == "chat":
            task = asyncio.create_task(self._handle_chat(ws, msg))
            sid = msg.get("session_id") or ""
            if sid:
                self._active_tasks[sid] = task
            task.add_done_callback(
                lambda t: self._active_tasks.pop(sid, None)
            )

        elif mtype == "memory_fetch":
            asyncio.create_task(self._handle_memory_fetch(ws, msg))

        elif mtype == "health_poll":
            health = self._orch.health()
            await self._send(ws, {"type": "health", **health})
            # Push escalation event if pending approvals exist
            if health.get("escalations_pending", 0) > 0:
                await self._send(ws, {"type": "escalation", "count": health["escalations_pending"]})

        elif mtype == "mode_change":
            mode = msg.get("mode", "")
            ok = self._orch.set_mode(mode)
            await self._send(ws, {
                "type": "mode_changed" if ok else "error",
                "mode": self._orch.current_mode,
                "code": "invalid_mode" if not ok else None,
                "message": f"Unknown mode: {mode!r}" if not ok else None,
            })

        elif mtype == "cancel":
            sid = msg.get("session_id")
            if sid and sid in self._active_tasks:
                self._active_tasks[sid].cancel()
                logger.info("Session cancelled", session_id=sid)

        else:
            await self._send(ws, {
                "type": "error",
                "code": "unknown_type",
                "message": f"Unknown message type: {mtype!r}",
            })

    # ------------------------------------------------------------------
    # Chat handler — runs orchestrator, streams events over WS
    # ------------------------------------------------------------------

    async def _handle_chat(self, ws: WebSocket, msg: dict) -> None:
        session_id = msg.get("session_id") or f"sess_{uuid.uuid4().hex[:8]}"
        user_input = msg.get("message", "").strip()
        mode = msg.get("mode") or self._orch.config.default_operating_mode

        if not user_input:
            await self._send(ws, {
                "type": "error",
                "session_id": session_id,
                "code": "empty_input",
                "message": "Empty message",
            })
            return

        # ── Persist user message ───────────────────────────────────────────
        if self._sessions is not None:
            try:
                self._sessions.add_message(session_id, "user", user_input)
            except Exception as _exc:
                logger.debug("session_store user write failed: %s", _exc)

        # ── Register an event callback so we can forward orchestrator events ──
        async def push_event(event: dict) -> None:
            """Translate orchestrator events into WS messages."""
            etype = event.get("type")

            if etype == "task_start":
                await self._send(ws, {
                    "type": "agent_status",
                    "session_id": session_id,
                    "agent": event.get("agent", "worker"),
                    "phase": "running",
                })
            elif etype == "task_done":
                await self._send(ws, {
                    "type": "agent_status",
                    "session_id": session_id,
                    "agent": event.get("agent", "worker"),
                    "phase": "done",
                })
            elif etype == "step":
                await self._send(ws, {
                    "type": "agent_status",
                    "session_id": session_id,
                    "agent": event.get("name", ""),
                    "phase": "running",
                })

        # Wrap async push_event in a sync callback for the orchestrator
        def sync_callback(event: dict) -> None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(push_event(event))
            except Exception:
                pass

        self._orch.add_event_callback(sync_callback)

        # Notify: starting
        await self._send(ws, {
            "type": "agent_status",
            "session_id": session_id,
            "agent": "orchestrator",
            "phase": "starting",
        })

        try:
            # Stream callback: each word arrives as a stream_delta event
            async def on_token(chunk: str) -> None:
                await self._send(ws, {
                    "type": "stream_delta",
                    "session_id": session_id,
                    "delta": chunk,
                })

            output = await self._orch.handle_request(
                user_input,
                operating_mode=mode,
                on_token=on_token,
            )

            # ── Persist assistant response ─────────────────────────────────
            if self._sessions is not None:
                try:
                    self._sessions.add_message(
                        session_id, "assistant", str(output.result or "")
                    )
                except Exception as _exc:
                    logger.debug("session_store assistant write failed: %s", _exc)

            # Send completion metadata
            await self._send(ws, {
                "type": "stream_done",
                "session_id": session_id,
                "status": output.status.value,
                "confidence": output.confidence,
                "tokens": output.tokens_used,
                "mode": output.data.get("operating_mode", mode),
                "requires_human_review": output.requires_human_review,
                "tasks_completed": output.data.get("tasks_completed", 1),
            })

            # Push updated health after each request
            health = self._orch.health()
            await self._send(ws, {"type": "health", **health})
            # Push escalation event if new approvals appeared after this request
            if output.requires_human_review or health.get("escalations_pending", 0) > 0:
                await self._send(ws, {
                    "type": "escalation",
                    "count": health.get("escalations_pending", 0),
                    "session_id": session_id,
                })

        except asyncio.CancelledError:
            await self._send(ws, {
                "type": "error",
                "session_id": session_id,
                "code": "cancelled",
                "message": "Request was cancelled.",
            })
        except Exception as exc:
            logger.error("Chat handler failed", session_id=session_id, error=str(exc))
            await self._send(ws, {
                "type": "error",
                "session_id": session_id,
                "code": "execution_error",
                "message": str(exc),
            })
        finally:
            self._orch.remove_event_callback(sync_callback)

    # ------------------------------------------------------------------
    # Memory fetch handler
    # ------------------------------------------------------------------

    async def _handle_memory_fetch(self, ws: WebSocket, msg: dict) -> None:
        """Fetch memory domain contents and push to client."""
        domain = msg.get("domain", "operational")
        try:
            keys = await self._orch._memory.list_keys(domain)
            records: dict[str, Any] = {}
            for k in keys[:20]:   # Cap at 20 records
                val = await self._orch._memory.read(domain, k)
                if val is not None:
                    records[k] = val
            await self._send(ws, {
                "type": "memory_data",
                "domain": domain,
                "keys": keys[:20],
                "records": records,
            })
        except Exception as exc:
            await self._send(ws, {
                "type": "error",
                "code": "memory_error",
                "message": str(exc),
            })

    # ------------------------------------------------------------------
    # Send helper
    # ------------------------------------------------------------------

    @staticmethod
    async def _send(ws: WebSocket, data: dict) -> None:
        """Serialise and send a JSON message; silently ignore closed sockets."""
        try:
            await ws.send_text(json.dumps(data, default=str))
        except Exception:
            pass
