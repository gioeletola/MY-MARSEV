"""
Physical action loop — perception → intent → device_gateway → action → memory.

Connects:
  - CameraFeed / FaceTracker (perception inputs)
  - SensorManager (environmental context)
  - DeviceGateway (output actions)
  - MemoryManager (write results to operational memory)
  - AdaptiveSilence (suppress when user in deep focus)
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Intent constants
INTENT_PRESENT = "present"
INTENT_ABSENT = "absent"
INTENT_FOCUS = "focus"
INTENT_AVAILABLE = "available"
INTENT_IDLE = "idle"

IntentHandler = Callable[[str, dict], Awaitable[None]]


class ActionLoop:
    """
    Drives the perception → intent → action cycle for physical presence.

    The loop:
      1. Polls SensorManager for an environmental snapshot.
      2. Reads the latest face/presence data (FaceData dict or None).
      3. Infers an intent string from those signals.
      4. Dispatches to registered async handler(s).
      5. Writes results to MemoryManager (operational domain).
    """

    def __init__(
        self,
        device_gateway,
        sensor_manager,
        memory_manager,
        adaptive_silence=None,
    ) -> None:
        self._gateway = device_gateway
        self._sensors = sensor_manager
        self._memory = memory_manager
        self._silence = adaptive_silence

        self._handlers: dict[str, list[IntentHandler]] = {}
        self._running = False
        self._started_at: float = 0.0
        self._intents_processed: int = 0
        self._last_intent: str = INTENT_IDLE

        # Register built-in handlers
        self.register_intent_handler(INTENT_ABSENT, self._handle_absent)
        self.register_intent_handler(INTENT_FOCUS, self._handle_focus)
        self.register_intent_handler(INTENT_AVAILABLE, self._handle_available)

    # ── Handler registration ───────────────────────────────────────────────

    def register_intent_handler(
        self, intent_name: str, handler_fn: IntentHandler
    ) -> None:
        """Register an async handler for a named intent.

        Multiple handlers per intent are supported; they are called in order.

        Args:
            intent_name: One of "present", "absent", "focus", "available", "idle".
            handler_fn: ``async (intent, context) → None``.
        """
        self._handlers.setdefault(intent_name, []).append(handler_fn)

    # ── Core processing ────────────────────────────────────────────────────

    async def process_frame(
        self,
        face_data: dict | None,
        sensor_snapshot: dict,
    ) -> str:
        """Given current face and sensor data, detect and execute intent.

        Returns the detected intent string.
        """
        intent = self.detect_intent(face_data, sensor_snapshot)
        await self.execute_intent(intent, {"face": face_data, "sensors": sensor_snapshot})
        return intent

    def detect_intent(
        self,
        face_data: dict | None,
        sensors: dict,
    ) -> str:
        """Infer an intent string from perception + sensor signals.

        Rules (evaluated in priority order):
        - face_detected=True, attention>=0.8  → "focus"
        - face_detected=True, attention>=0.4  → "present"
        - face_detected=True (low attention)  → "available"
        - face_detected=False, cpu_percent<5  → "absent"
        - face_detected=False                 → "idle"
        """
        if not face_data:
            cpu = sensors.get("cpu_percent", 100.0) or 100.0
            if cpu < 5.0:
                return INTENT_ABSENT
            return INTENT_IDLE

        detected = face_data.get("detected", False)
        attention = face_data.get("attention", 0.0) or 0.0

        if not detected:
            cpu = sensors.get("cpu_percent", 100.0) or 100.0
            return INTENT_ABSENT if cpu < 5.0 else INTENT_IDLE

        if attention >= 0.8:
            return INTENT_FOCUS
        if attention >= 0.4:
            return INTENT_PRESENT
        return INTENT_AVAILABLE

    async def execute_intent(self, intent: str, context: dict | None = None) -> None:
        """Dispatch *intent* to all registered handlers.

        Also writes the intent event to MemoryManager if available.
        """
        ctx = context or {}
        self._last_intent = intent
        self._intents_processed += 1

        handlers = self._handlers.get(intent, [])
        for handler in handlers:
            try:
                await handler(intent, ctx)
            except Exception as exc:
                logger.warning(
                    "Intent handler error (intent=%s): %s", intent, exc
                )

        # Persist to memory
        if self._memory:
            try:
                await self._memory.store(
                    domain="operational",
                    key=f"action_loop:intent:{int(time.time())}",
                    value={"intent": intent, "context": ctx},
                )
            except Exception as exc:
                logger.debug("Memory write skipped: %s", exc)

    # ── Main async loop ────────────────────────────────────────────────────

    async def run_loop(self, stop_event: asyncio.Event | None = None) -> None:
        """Async loop: snapshot sensors every 5 s, detect intent, execute.

        Args:
            stop_event: Set to stop the loop cleanly.
        """
        self._running = True
        self._started_at = time.time()
        logger.info("ActionLoop started")

        while self._running:
            if stop_event and stop_event.is_set():
                break

            try:
                sensors = self._sensors.snapshot() if self._sensors else {}

                # Try to get face data if a face tracker is wired up
                face_data = await self._get_face_data()

                # Check adaptive silence — skip execution if in deep focus
                if self._silence and await self._is_suppressed():
                    logger.debug("ActionLoop suppressed by AdaptiveSilence")
                    await asyncio.sleep(5.0)
                    continue

                intent = await self.process_frame(face_data, sensors)
                logger.debug("ActionLoop: intent=%s", intent)

            except Exception as exc:
                logger.warning("ActionLoop iteration error: %s", exc)

            await asyncio.sleep(5.0)

        self._running = False
        logger.info("ActionLoop stopped")

    # ── Built-in intent handlers ───────────────────────────────────────────

    async def _handle_absent(self, intent: str, context: dict) -> None:
        """Turn off lights via Home Assistant when user leaves."""
        logger.info("ActionLoop: user absent — requesting lights off")
        try:
            await self._gateway.hass_call_service(
                domain="light",
                service="turn_off",
                entity_id="light.all",
            )
        except Exception as exc:
            logger.debug("HA lights off skipped: %s", exc)

    async def _handle_focus(self, intent: str, context: dict) -> None:
        """Activate silent mode when user is in deep focus."""
        logger.info("ActionLoop: user in focus — activating silent mode")
        if self._silence:
            try:
                await self._silence.enable()
            except Exception as exc:
                logger.debug("AdaptiveSilence.enable() error: %s", exc)

    async def _handle_available(self, intent: str, context: dict) -> None:
        """Restore notifications when user is available."""
        logger.info("ActionLoop: user available — restoring notifications")
        if self._silence:
            try:
                await self._silence.disable()
            except Exception as exc:
                logger.debug("AdaptiveSilence.disable() error: %s", exc)

    # ── Internal helpers ───────────────────────────────────────────────────

    async def _get_face_data(self) -> dict | None:
        """Attempt to read face data from any registered face tracker."""
        # FaceTracker instances can be injected via set_face_tracker()
        tracker = getattr(self, "_face_tracker", None)
        if tracker is None:
            return None
        try:
            fd = await tracker.get_frame()
            return {
                "detected": fd.detected,
                "x": fd.x,
                "y": fd.y,
                "size": fd.size,
                "gaze_direction": fd.gaze_direction,
                "attention": fd.attention,
            }
        except Exception as exc:
            logger.debug("Face tracker read error: %s", exc)
            return None

    async def _is_suppressed(self) -> bool:
        """Return True if AdaptiveSilence wants to suppress action."""
        try:
            return bool(await self._silence.is_active())
        except Exception:
            return False

    def set_face_tracker(self, tracker) -> None:
        """Wire a FaceTracker instance into the loop."""
        self._face_tracker = tracker

    # ── Diagnostics ───────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return operational statistics for the loop."""
        uptime = time.time() - self._started_at if self._started_at else 0.0
        return {
            "intents_processed": self._intents_processed,
            "last_intent": self._last_intent,
            "uptime": uptime,
            "running": self._running,
        }
