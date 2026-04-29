"""Orchestrator bridge — coordinates all HUD subsystems and relays events to the orchestrator."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class HUDEvent:
    source: str
    event_type: str
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class HUDStatus:
    camera_active: bool = False
    face_detected: bool = False
    clap_detected: bool = False
    voice_listening: bool = False
    overlay_visible: bool = False
    bridge_running: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


# ── HUD Orchestrator ──────────────────────────────────────────────────────────

class HUDOrchestrator:
    """
    Coordinates all HUD subsystems (camera, face tracker, clap detector, voice
    recogniser, overlay) and exposes a unified async event stream.
    """

    def __init__(
        self,
        orchestrator: Any,
        camera_feed: Any = None,
        face_tracker: Any = None,
        clap_system: Any = None,
        voice_recogniser: Any = None,
        overlay_ui: Any = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._camera = camera_feed
        self._face = face_tracker
        self._clap = clap_system
        self._voice = voice_recogniser
        self._overlay = overlay_ui

        self._callbacks: list[EventCallback] = []
        self._running = False
        self._stop_event: asyncio.Event = asyncio.Event()
        self._event_queue: asyncio.Queue[HUDEvent] = asyncio.Queue(maxsize=256)

        self._status = HUDStatus()
        self._tasks: list[asyncio.Task] = []

    # ── Status ────────────────────────────────────────────────────────────

    def get_status(self) -> HUDStatus:
        return HUDStatus(
            camera_active=self._camera is not None and getattr(self._camera, "_running", False),
            face_detected=getattr(self._face, "_last_detected", False),
            clap_detected=getattr(self._clap, "_active", False),
            voice_listening=getattr(self._voice, "_running", False),
            overlay_visible=self._overlay is not None,
            bridge_running=self._running,
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """Return True if the orchestrator is currently active."""
        return self._running

    def event_queue(self) -> asyncio.Queue:
        """Expose the internal event queue for external consumers."""
        return self._event_queue

    async def start_all(self, dry_run: bool = False) -> None:
        """Start all subsystems and the internal event loop.

        Args:
            dry_run: When True, mark as running but skip all hardware init.
                     Useful for testing without real devices attached.
        """
        if self._running:
            logger.warning("HUDOrchestrator: already running")
            return

        self._running = True
        self._stop_event.clear()
        self._status.bridge_running = True
        logger.info("HUDOrchestrator: starting all subsystems (dry_run=%s)", dry_run)

        if dry_run:
            # In dry-run mode we do not spawn any tasks or touch hardware.
            return

        if self._camera:
            t = asyncio.create_task(
                self._camera.run_loop(self._stop_event), name="hud_camera"
            )
            self._tasks.append(t)

        if self._clap:
            if self._clap._available:
                t = asyncio.create_task(self._clap.start(), name="hud_clap")
                self._tasks.append(t)
                self._clap.on_clap(self._on_clap)

        if self._voice:
            if hasattr(self._voice, "add_handler"):
                self._voice.add_handler(self._on_voice)
            t = asyncio.create_task(self._voice.start(), name="hud_voice")
            self._tasks.append(t)

        # face polling loop
        t = asyncio.create_task(self._face_poll_loop(), name="hud_face")
        self._tasks.append(t)

        # health push loop
        t = asyncio.create_task(self._health_loop(), name="hud_health")
        self._tasks.append(t)

        logger.info("HUDOrchestrator: all subsystems started (%d tasks)", len(self._tasks))

    async def stop_all(self) -> None:
        """Gracefully stop all subsystems."""
        logger.info("HUDOrchestrator: stopping all subsystems")
        self._running = False
        self._stop_event.set()

        if self._camera:
            self._camera.stop()
        if self._clap:
            await self._clap.stop()
        if self._voice:
            self._voice.stop()

        for t in self._tasks:
            if not t.done():
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        self._tasks.clear()
        self._status.bridge_running = False
        logger.info("HUDOrchestrator: stopped")

    # ── Event stream ──────────────────────────────────────────────────────

    async def event_stream(self) -> AsyncIterator[HUDEvent]:
        """Async generator yielding HUDEvent objects from all subsystems."""
        while self._running or not self._event_queue.empty():
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue

    def on_event(self, callback: EventCallback) -> None:
        self._callbacks.append(callback)

    async def emit(self, event: dict[str, Any]) -> None:
        for cb in self._callbacks:
            try:
                await cb(event)
            except Exception as exc:
                logger.warning("HUDOrchestrator event callback failed: %s", exc)

    async def _enqueue(self, source: str, event_type: str, data: dict) -> None:
        ev = HUDEvent(source=source, event_type=event_type, data=data)
        try:
            self._event_queue.put_nowait(ev)
        except asyncio.QueueFull:
            logger.debug("HUDOrchestrator: event queue full, dropping %s/%s", source, event_type)
        await self.emit(ev.to_dict())

    # ── Subsystem callbacks ───────────────────────────────────────────────

    async def _on_clap(self) -> None:
        self._status.clap_detected = True
        await self._enqueue("clap_system", "clap_detected", {"action": "toggle_overlay"})

    async def _on_voice(self, text: str, confidence: float) -> None:
        await self._enqueue("voice_command", "voice_recognised", {
            "text": text,
            "confidence": confidence,
        })
        if text.strip() and self._orchestrator:
            await self.handle_hud_command(text)

    async def _face_poll_loop(self) -> None:
        while self._running:
            if self._stop_event.is_set():
                break
            if self._face:
                try:
                    face_data = await self._face.get_frame()
                    detected = getattr(face_data, "detected", False)
                    if detected != self._status.face_detected:
                        self._status.face_detected = detected
                        await self._enqueue("face_tracker", "face_status", {
                            "detected": detected,
                            "x": getattr(face_data, "x", 0.5),
                            "y": getattr(face_data, "y", 0.5),
                        })
                except Exception as exc:
                    logger.debug("HUDOrchestrator face poll: %s", exc)
            await asyncio.sleep(0.5)

    async def _health_loop(self) -> None:
        while self._running:
            if self._stop_event.is_set():
                break
            await self._health_push()
            await asyncio.sleep(10.0)

    async def _health_push(self) -> None:
        if not self._orchestrator:
            return
        try:
            health = self._orchestrator.health()
            await self._enqueue("orchestrator", "health", health)
        except Exception as exc:
            logger.debug("HUDOrchestrator health push: %s", exc)

    # ── Command handling ──────────────────────────────────────────────────

    async def handle_hud_command(self, command: str, mode: str = "command") -> None:
        if not self._orchestrator:
            await self._enqueue("orchestrator", "error", {"message": "Orchestrator not ready"})
            return
        try:
            await self._enqueue("orchestrator", "agent_status", {
                "agent_id": "ceo_agent", "status": "running"
            })
            result = await self._orchestrator.handle_request(command)
            output = result.result if hasattr(result, "result") else str(result)
            for i in range(0, len(output), 50):
                chunk = output[i:i + 50]
                await self.emit({"type": "stream_delta", "content": chunk})
                await asyncio.sleep(0.01)
            await self.emit({
                "type": "stream_done",
                "tokens": getattr(result, "tokens_used", {}).get("total", 0),
                "confidence": getattr(result, "confidence", 0.8),
            })
            await self._enqueue("orchestrator", "agent_status", {
                "agent_id": "ceo_agent", "status": "done"
            })
        except Exception as exc:
            await self._enqueue("orchestrator", "error", {"message": str(exc)})


# ── Legacy OrchestratorBridge (kept for backwards compat) ─────────────────────

class OrchestratorBridge:
    """Legacy relay bridge — use HUDOrchestrator for new code."""

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator
        self._callbacks: list[EventCallback] = []
        self._running = False
        self._queue: asyncio.Queue = asyncio.Queue()

    def on_event(self, callback: EventCallback) -> None:
        self._callbacks.append(callback)

    async def emit(self, event: dict[str, Any]) -> None:
        for cb in self._callbacks:
            try:
                await cb(event)
            except Exception as exc:
                logger.warning("HUD event callback failed: %s", exc)

    async def handle_hud_command(self, command: str, mode: str = "command") -> None:
        if not self._orchestrator:
            await self.emit({"type": "error", "message": "Orchestrator not ready"})
            return
        try:
            await self.emit({"type": "agent_status", "agent_id": "ceo_agent", "status": "running"})
            result = await self._orchestrator.handle_request(command)
            output = result.result if hasattr(result, "result") else str(result)
            for i in range(0, len(output), 50):
                chunk = output[i:i + 50]
                await self.emit({"type": "stream_delta", "content": chunk})
                await asyncio.sleep(0.01)
            await self.emit({
                "type": "stream_done",
                "tokens": getattr(result, "tokens_used", {}).get("total", 0),
                "confidence": getattr(result, "confidence", 0.8),
            })
            await self.emit({"type": "agent_status", "agent_id": "ceo_agent", "status": "done"})
        except Exception as exc:
            await self.emit({"type": "error", "message": str(exc)})

    async def health_push(self) -> None:
        if not self._orchestrator:
            return
        try:
            health = self._orchestrator.health()
            await self.emit({"type": "health", "data": health})
        except Exception as exc:
            logger.warning("Health push failed: %s", exc)

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        self._running = True
        while self._running:
            if stop_event and stop_event.is_set():
                break
            await self.health_push()
            await asyncio.sleep(10.0)

    def stop(self) -> None:
        self._running = False
