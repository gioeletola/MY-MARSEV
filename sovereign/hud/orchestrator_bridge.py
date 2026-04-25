"""Orchestrator bridge — WebSocket relay between HUD and the sovereign orchestrator."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


class OrchestratorBridge:
    """
    Maintains a live connection between the HUD (browser / native overlay) and
    the sovereign orchestrator. Translates HUD events into orchestrator calls
    and streams agent activity back to the HUD.
    """

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
        """Process a voice/text command from the HUD."""
        if not self._orchestrator:
            await self.emit({"type": "error", "message": "Orchestrator not ready"})
            return
        try:
            await self.emit({"type": "agent_status", "agent_id": "ceo_agent", "status": "running"})
            # Delegate to orchestrator
            result = await self._orchestrator.handle_request(command)
            output = result.result if hasattr(result, "result") else str(result)
            # Stream back in chunks
            for i in range(0, len(output), 50):
                chunk = output[i:i+50]
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
        """Push a health snapshot to the HUD."""
        if not self._orchestrator:
            return
        try:
            health = self._orchestrator.health()
            await self.emit({"type": "health", "data": health})
        except Exception as exc:
            logger.warning("Health push failed: %s", exc)

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        """Periodic health push loop."""
        self._running = True
        while self._running:
            if stop_event and stop_event.is_set():
                break
            await self.health_push()
            await asyncio.sleep(10.0)

    def stop(self) -> None:
        self._running = False
