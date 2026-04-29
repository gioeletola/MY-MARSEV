"""
Timer tool — create timers, stopwatches, and countdowns.

Uses in-memory dict keyed by timer_id. Thread-safe with threading.Lock.
No external dependencies.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_timers: dict[str, dict[str, Any]] = {}


def _format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    if seconds < 0:
        seconds = 0.0
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int((seconds - total) * 1000)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    if millis and not hours and not minutes:
        parts.append(f"{millis}ms")
    return " ".join(parts)


class TimerTool(BaseTool):
    """
    Stopwatch / timer / countdown utility.

    Timers are stored in-memory and identified by a user-supplied timer_id.
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="timer_tool",
            description=(
                "Start, stop, and query timers / stopwatches in memory. "
                "Returns formatted duration strings (e.g. '2h 34m 12s')."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "elapsed", "countdown", "list"],
                        "description": (
                            "'start' — begin a new timer; "
                            "'stop' — stop a running timer; "
                            "'elapsed' — query elapsed time without stopping; "
                            "'countdown' — compute remaining time for a countdown; "
                            "'list' — list all active timers."
                        ),
                    },
                    "timer_id": {
                        "type": "string",
                        "description": "Unique name / ID for the timer (required except for list).",
                    },
                    "duration_seconds": {
                        "type": "number",
                        "description": "Countdown duration in seconds (required for countdown).",
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional human-readable label for the timer.",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str,
        timer_id: str = "",
        duration_seconds: float = 0.0,
        label: str = "",
        **_: Any,
    ) -> Any:
        """Execute a timer operation."""
        try:
            if action == "start":
                if not timer_id:
                    return {"error": "timer_id is required for start"}
                with _lock:
                    if timer_id in _timers and _timers[timer_id].get("running"):
                        return {"error": f"Timer '{timer_id}' is already running"}
                    _timers[timer_id] = {
                        "timer_id": timer_id,
                        "label": label or timer_id,
                        "start_time": time.monotonic(),
                        "stop_time": None,
                        "running": True,
                    }
                logger.info("TimerTool.start id=%s", timer_id)
                return {
                    "action": "start",
                    "timer_id": timer_id,
                    "label": label or timer_id,
                    "started": True,
                    "error": None,
                }

            if action == "stop":
                if not timer_id:
                    return {"error": "timer_id is required for stop"}
                with _lock:
                    if timer_id not in _timers:
                        return {"error": f"Timer '{timer_id}' not found"}
                    t = _timers[timer_id]
                    if not t["running"]:
                        return {"error": f"Timer '{timer_id}' is not running"}
                    stop_ts = time.monotonic()
                    t["stop_time"] = stop_ts
                    t["running"] = False
                    elapsed = stop_ts - t["start_time"]
                return {
                    "action": "stop",
                    "timer_id": timer_id,
                    "elapsed_seconds": elapsed,
                    "elapsed_formatted": _format_duration(elapsed),
                    "error": None,
                }

            if action == "elapsed":
                if not timer_id:
                    return {"error": "timer_id is required for elapsed"}
                with _lock:
                    if timer_id not in _timers:
                        return {"error": f"Timer '{timer_id}' not found"}
                    t = _timers[timer_id]
                    if t["running"]:
                        elapsed = time.monotonic() - t["start_time"]
                    else:
                        elapsed = t["stop_time"] - t["start_time"]  # type: ignore[operator]
                return {
                    "action": "elapsed",
                    "timer_id": timer_id,
                    "running": t["running"],
                    "elapsed_seconds": elapsed,
                    "elapsed_formatted": _format_duration(elapsed),
                    "error": None,
                }

            if action == "countdown":
                if not timer_id:
                    return {"error": "timer_id is required for countdown"}
                if duration_seconds <= 0:
                    return {"error": "duration_seconds must be > 0 for countdown"}
                with _lock:
                    if timer_id not in _timers:
                        return {"error": f"Timer '{timer_id}' not found; start it first"}
                    t = _timers[timer_id]
                    elapsed = time.monotonic() - t["start_time"]
                remaining = max(0.0, duration_seconds - elapsed)
                expired = remaining == 0.0
                return {
                    "action": "countdown",
                    "timer_id": timer_id,
                    "duration_seconds": duration_seconds,
                    "elapsed_seconds": elapsed,
                    "remaining_seconds": remaining,
                    "remaining_formatted": _format_duration(remaining),
                    "expired": expired,
                    "error": None,
                }

            if action == "list":
                with _lock:
                    snapshot = list(_timers.values())
                now = time.monotonic()
                result = []
                for t in snapshot:
                    if t["running"]:
                        elapsed = now - t["start_time"]
                    else:
                        elapsed = (t["stop_time"] or t["start_time"]) - t["start_time"]
                    result.append({
                        "timer_id": t["timer_id"],
                        "label": t["label"],
                        "running": t["running"],
                        "elapsed_formatted": _format_duration(elapsed),
                    })
                return {
                    "action": "list",
                    "timers": result,
                    "count": len(result),
                    "error": None,
                }

            return {"error": f"Unknown action: {action}"}

        except Exception as exc:
            logger.error("TimerTool error action=%s: %s", action, exc)
            return {"result": None, "error": str(exc)}
