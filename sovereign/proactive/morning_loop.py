"""Proactive morning loop — builds a daily brief and delivers it via Telegram."""
from __future__ import annotations

import datetime
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class MorningLoop:
    """Builds and delivers a daily morning brief.

    Triggered by the scheduler (default 07:00 daily).
    Collects today's calendar events and urgent tasks, formats them, and
    delivers via Telegram. Also persists the brief to the operational memory
    domain.
    """

    def __init__(
        self,
        orchestrator: Any | None = None,
        hour: int | None = None,
        minute: int = 0,
    ) -> None:
        self._orc = orchestrator
        self._hour = hour if hour is not None else int(os.getenv("SOVEREIGN_MORNING_HOUR", "7"))
        self._minute = minute
        self._tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._tg_chat  = os.getenv("TELEGRAM_CHAT_ID", "")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self) -> str:
        """Build and deliver the morning brief. Returns the brief text."""
        brief = await self._build_brief()
        await self._deliver(brief)
        await self._save_to_memory(brief)
        return brief

    # ------------------------------------------------------------------
    # Brief building
    # ------------------------------------------------------------------

    async def _build_brief(self) -> str:
        today = datetime.date.today().strftime("%A %d %B %Y")
        lines = [f"☀️ *SOVEREIGN Morning Brief — {today}*\n"]

        events = await self._fetch_calendar_events()
        if events:
            lines.append("\U0001f4c5 *Today's Calendar*")
            for e in events[:5]:
                title = e.get("summary", e.get("title", "Event"))
                start = e.get("dtstart", e.get("start", {}) or {})
                if isinstance(start, dict):
                    start = start.get("dateTime", start.get("date", ""))
                time_str = str(start)[11:16] if len(str(start)) > 10 else ""
                lines.append(f"  • {time_str} {title}")
            lines.append("")

        tasks = await self._fetch_urgent_tasks()
        if tasks:
            lines.append("⚡ *Urgent Tasks*")
            for t in tasks[:5]:
                lines.append(f"  • {t}")
            lines.append("")

        lines.append("_Have a focused day. — SOVEREIGN_")
        return "\n".join(lines)

    async def _fetch_calendar_events(self) -> list[dict]:
        if not self._orc:
            return []
        try:
            registry = getattr(self._orc, "_connector_registry", None)
            if registry:
                cal = registry.get("calendar")
                if cal:
                    return await cal.get_today_events()
        except Exception as exc:
            logger.debug("MorningLoop: calendar fetch failed: %s", exc)
        return []

    async def _fetch_urgent_tasks(self) -> list[str]:
        if not self._orc:
            return []
        try:
            memory = getattr(self._orc, "_memory", None)
            if memory:
                keys = await memory.list_keys("next_action")
                tasks: list[str] = []
                for k in keys[:10]:
                    record = await memory.read("next_action", k)
                    if isinstance(record, dict):
                        title = record.get("title") or record.get("task") or k
                        tasks.append(str(title))
                return tasks
        except Exception as exc:
            logger.debug("MorningLoop: task fetch failed: %s", exc)
        return []

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    async def _deliver(self, brief: str) -> None:
        if not self._tg_token or not self._tg_chat:
            logger.info("MorningLoop: Telegram not configured, skipping delivery")
            return
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{self._tg_token}/sendMessage",
                    json={
                        "chat_id": self._tg_chat,
                        "text": brief,
                        "parse_mode": "Markdown",
                    },
                )
        except Exception as exc:
            logger.warning("MorningLoop: Telegram delivery failed: %s", exc)

    async def _save_to_memory(self, brief: str) -> None:
        if not self._orc:
            return
        try:
            memory = getattr(self._orc, "_memory", None)
            if memory:
                key = datetime.date.today().isoformat()
                await memory.write("operational", f"morning_brief_{key}", {
                    "brief": brief,
                    "date": key,
                    "created_at": datetime.datetime.utcnow().isoformat() + "Z",
                })
        except Exception as exc:
            logger.debug("MorningLoop: memory save failed: %s", exc)
