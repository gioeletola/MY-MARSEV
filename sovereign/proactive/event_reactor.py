"""
ProactiveEventReactor — subscribes to the EventBus and triggers agent
actions or notifications in response to system events.

Wired pairs (EventType → reaction):
  APPROVAL_REQUIRED  → Telegram notification to TELEGRAM_CHAT_ID
  SECURITY_ALERT     → Telegram + memory write to 'security' domain
  TASK_FAILED        → escalation log + optional Telegram
  HEALTH_UPDATE      → Telegram alert if overall status is 'degraded'/'critical'
  JOB_COMPLETE       → memory write to 'operational' domain
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.events.event_bus import EventBus
from sovereign.events.event_types import EventType, SovereignEvent

logger = logging.getLogger(__name__)


class ProactiveEventReactor:
    """
    Subscribes to the orchestrator's EventBus and triggers side-effects
    (Telegram notifications, memory writes, escalations) when key events fire.

    Usage::
        reactor = ProactiveEventReactor(orchestrator)
        reactor.attach(orchestrator.event_bus)   # call once at startup
        # From this point all matching events auto-trigger reactions
    """

    def __init__(self, orchestrator: Any) -> None:
        self._orch = orchestrator
        self._tg_token  = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._tg_chat   = os.getenv("TELEGRAM_CHAT_ID", "")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def attach(self, bus: EventBus) -> None:
        """Subscribe all reaction handlers to the bus."""
        bus.subscribe(EventType.APPROVAL_REQUIRED, self._on_approval_required)
        bus.subscribe(EventType.SECURITY_ALERT,    self._on_security_alert)
        bus.subscribe(EventType.TASK_FAILED,       self._on_task_failed)
        bus.subscribe(EventType.HEALTH_UPDATE,     self._on_health_update)
        bus.subscribe(EventType.JOB_COMPLETE,      self._on_job_complete)
        logger.info("ProactiveEventReactor attached — 5 event hooks active")

    def detach(self, bus: EventBus) -> None:
        """Unsubscribe all handlers."""
        bus.unsubscribe(EventType.APPROVAL_REQUIRED, self._on_approval_required)
        bus.unsubscribe(EventType.SECURITY_ALERT,    self._on_security_alert)
        bus.unsubscribe(EventType.TASK_FAILED,       self._on_task_failed)
        bus.unsubscribe(EventType.HEALTH_UPDATE,     self._on_health_update)
        bus.unsubscribe(EventType.JOB_COMPLETE,      self._on_job_complete)

    # ------------------------------------------------------------------
    # Handlers (all async — scheduled on the running loop by EventBus.emit)
    # ------------------------------------------------------------------

    async def _on_approval_required(self, event: SovereignEvent) -> None:
        """Send Telegram message when human approval is needed."""
        task_id = event.data.get("task_id", "?")
        agent   = event.data.get("agent_id", "unknown")
        action  = event.data.get("action", "EXECUTE-class action")
        msg = (
            f"⚠️ *MARSEV — Approvazione richiesta*\n"
            f"Agente: `{agent}`\n"
            f"Azione: `{action}`\n"
            f"Task ID: `{task_id}`\n\n"
            f"Approva o rifiuta dalla web UI."
        )
        await self._telegram(msg)
        logger.info("APPROVAL_REQUIRED notification sent for task=%s", task_id)

    async def _on_security_alert(self, event: SovereignEvent) -> None:
        """Telegram + memory write on security events."""
        severity = event.data.get("severity", "HIGH")
        detail   = event.data.get("detail", "Security event detected")
        msg = (
            f"🚨 *MARSEV — Security Alert [{severity}]*\n"
            f"{detail}\n"
            f"Session: `{event.session_id}`"
        )
        await self._telegram(msg)
        await self._memory_write("operational", f"security_alert_{event.ts:.0f}", {
            "severity": severity, "detail": detail,
            "session_id": event.session_id, "ts": event.ts,
        })
        logger.warning("SECURITY_ALERT reaction: severity=%s", severity)

    async def _on_task_failed(self, event: SovereignEvent) -> None:
        """Log task failures; notify via Telegram for critical agents."""
        task_id = event.data.get("task_id", "?")
        agent   = event.data.get("agent_id", "unknown")
        error   = event.data.get("error", "unknown error")
        await self._memory_write("operational", f"task_failed_{task_id}", {
            "agent": agent, "error": error,
            "session_id": event.session_id, "ts": event.ts,
        })
        # Only page via Telegram for executive/chief agents
        _CRITICAL_AGENTS = {"ceo", "chief_of_staff", "guardian", "imperial_commander",
                            "security_sentinel", "incident_response"}
        if agent in _CRITICAL_AGENTS:
            msg = (
                f"❌ *MARSEV — Task fallito*\n"
                f"Agente: `{agent}`\n"
                f"Errore: `{error[:200]}`"
            )
            await self._telegram(msg)

    async def _on_health_update(self, event: SovereignEvent) -> None:
        """Alert via Telegram when overall system health is degraded or critical."""
        overall = event.data.get("overall", "healthy")
        if overall in ("degraded", "critical", "error"):
            alerts = event.data.get("alerts", [])
            alert_txt = "\n".join(f"• {a}" for a in alerts[:5]) if alerts else "—"
            msg = (
                f"{'⚠️' if overall == 'degraded' else '🔴'} "
                f"*MARSEV — Health {overall.upper()}*\n{alert_txt}"
            )
            await self._telegram(msg)

    async def _on_job_complete(self, event: SovereignEvent) -> None:
        """Record completed scheduled jobs to memory."""
        job_id = event.data.get("job_id", "?")
        name   = event.data.get("name", "?")
        await self._memory_write("operational", f"job_complete_{job_id}_{event.ts:.0f}", {
            "job_id": job_id, "name": name, "ts": event.ts,
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _telegram(self, text: str) -> None:
        """Send a Telegram message, silently skipping if not configured."""
        if not self._tg_token or not self._tg_chat:
            logger.debug("Telegram not configured — skipping notification")
            return
        try:
            from sovereign.integrations.connectors.telegram_connector import TelegramConnector
            conn = TelegramConnector({
                "bot_token": self._tg_token,
                "chat_id": self._tg_chat,
            })
            await conn.send_message(text, parse_mode="Markdown")
        except Exception as exc:
            logger.error("ProactiveEventReactor: Telegram send failed: %s", exc)

    async def _memory_write(self, domain: str, key: str, value: dict) -> None:
        """Write to memory, silently skipping on failure."""
        try:
            memory = getattr(self._orch, "_memory", None)
            if memory is not None:
                await memory.write(domain, key, value)
        except Exception as exc:
            logger.debug("ProactiveEventReactor: memory write failed: %s", exc)
