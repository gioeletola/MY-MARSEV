"""
Telegram Bot — full bidirectional SOVEREIGN AI OS connector.

Routes Telegram messages → orchestrator → streamed replies back to chat.

Commands:
  /start    — welcome + capabilities
  /status   — system health
  /mode     — show / set operating mode  (/mode finance)
  /memory   — show memory snapshot
  /clear    — clear conversation history
  /help     — command list

Conversation history is persisted per chat_id so context survives restarts.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from sovereign.integrations.telegram_integration import TelegramIntegration
from sovereign.integrations.base_integration import IntegrationConfig

logger = logging.getLogger(__name__)

_HISTORY_FILE = Path("data/memory/telegram_history.json")
_MAX_HISTORY_PER_CHAT = 20


class ConversationHistory:
    """Persistent per-chat conversation history."""

    def __init__(self) -> None:
        self._data: dict[str, list[dict]] = {}
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if _HISTORY_FILE.exists():
            try:
                self._data = json.loads(_HISTORY_FILE.read_text())
            except Exception:
                self._data = {}

    def _save(self) -> None:
        try:
            _HISTORY_FILE.write_text(json.dumps(self._data, indent=2))
        except Exception as exc:
            logger.warning("Failed to save telegram history: %s", exc)

    def add(self, chat_id: str, role: str, content: str) -> None:
        key = str(chat_id)
        self._data.setdefault(key, [])
        self._data[key].append({"role": role, "content": content, "ts": time.time()})
        # Trim to max
        if len(self._data[key]) > _MAX_HISTORY_PER_CHAT * 2:
            self._data[key] = self._data[key][-_MAX_HISTORY_PER_CHAT * 2:]
        self._save()

    def get(self, chat_id: str) -> list[dict]:
        return self._data.get(str(chat_id), [])

    def clear(self, chat_id: str) -> None:
        self._data.pop(str(chat_id), None)
        self._save()

    def context_string(self, chat_id: str, max_turns: int = 6) -> str:
        history = self.get(chat_id)[-max_turns * 2:]
        if not history:
            return ""
        lines = []
        for msg in history:
            prefix = "User" if msg["role"] == "user" else "SOVEREIGN"
            lines.append(f"{prefix}: {msg['content']}")
        return "\n".join(lines)


class TelegramBot:
    """
    High-level bot that connects TelegramIntegration with the SOVEREIGN orchestrator.
    Run via: python main.py telegram
    """

    def __init__(self, orchestrator: Any, bot_token: str, allowed_chat_ids: str = "") -> None:
        self._orchestrator = orchestrator
        self._connector = TelegramIntegration()
        self._history = ConversationHistory()
        self._modes: dict[str, str] = {}   # per-chat active mode
        self._stop_event = asyncio.Event()

        config = IntegrationConfig(
            integration_id="telegram",
            name="Telegram Bot",
            credentials={"bot_token": bot_token},
            settings={"allowed_chat_ids": allowed_chat_ids},
            enabled=True,
        )
        self._connector.connect(config)
        self._register_handlers()

    def _register_handlers(self) -> None:
        self._connector.on_command("/start",  self._cmd_start)
        self._connector.on_command("/status", self._cmd_status)
        self._connector.on_command("/mode",   self._cmd_mode)
        self._connector.on_command("/memory", self._cmd_memory)
        self._connector.on_command("/clear",  self._cmd_clear)
        self._connector.on_command("/help",   self._cmd_help)
        self._connector.on_message(self._handle_message)

    # ── Command handlers ──────────────────────────────────────────────────

    async def _cmd_start(self, msg: dict) -> None:
        chat_id = msg["chat_id"]
        text = (
            "👋 <b>SOVEREIGN AI OS</b> — online.\n\n"
            "I'm your personal AI operating system. Send me any message and I'll route it to the right specialist agent.\n\n"
            "<b>Commands:</b>\n"
            "/status — system health\n"
            "/mode &lt;name&gt; — switch mode (finance, business, founder, war…)\n"
            "/memory — view memory snapshot\n"
            "/clear — clear conversation history\n"
            "/help — this message\n\n"
            "Current mode: <code>" + self._modes.get(str(chat_id), "command") + "</code>"
        )
        await self._connector.send_message(chat_id, text)

    async def _cmd_status(self, msg: dict) -> None:
        chat_id = msg["chat_id"]
        try:
            health = self._orchestrator.health()
            status = health.get("overall", "unknown").upper()
            agents = health.get("agents_registered", 0)
            mode = health.get("operating_mode", "—")
            text = (
                f"<b>System Status: {status}</b>\n\n"
                f"🤖 Agents registered: <code>{agents}</code>\n"
                f"⚙️ Mode: <code>{mode}</code>\n"
                f"🧠 Memory domains: <code>{health.get('memory_domains', 14)}</code>"
            )
        except Exception as exc:
            text = f"❌ Status check failed: {exc}"
        await self._connector.send_message(chat_id, text)

    async def _cmd_mode(self, msg: dict) -> None:
        chat_id = msg["chat_id"]
        args = msg.get("args", "").strip().lower()
        valid_modes = [
            "command", "business", "personal", "finance", "study", "travel",
            "research", "builder", "local_offline", "survival",
            "founder", "war", "prestige", "silent", "recovery", "emergency",
        ]
        if args and args in valid_modes:
            self._modes[str(chat_id)] = args
            await self._connector.send_message(chat_id, f"✓ Mode switched to <code>{args}</code>")
        elif args:
            await self._connector.send_message(
                chat_id,
                f"Unknown mode: <code>{args}</code>\n\nAvailable: {', '.join(valid_modes)}"
            )
        else:
            current = self._modes.get(str(chat_id), "command")
            await self._connector.send_message(
                chat_id,
                f"Current mode: <code>{current}</code>\n\nUse /mode &lt;name&gt; to switch."
            )

    async def _cmd_memory(self, msg: dict) -> None:
        chat_id = msg["chat_id"]
        try:
            snapshot = await self._orchestrator._memory.get_snapshot()
            lines = ["<b>Memory Snapshot</b>\n"]
            for domain, data in snapshot.items():
                count = len(data) if isinstance(data, dict) else 0
                lines.append(f"• <code>{domain}</code>: {count} entries")
            await self._connector.send_message(chat_id, "\n".join(lines))
        except Exception as exc:
            await self._connector.send_message(chat_id, f"❌ Memory error: {exc}")

    async def _cmd_clear(self, msg: dict) -> None:
        chat_id = msg["chat_id"]
        self._history.clear(str(chat_id))
        await self._connector.send_message(chat_id, "✓ Conversation history cleared.")

    async def _cmd_help(self, msg: dict) -> None:
        await self._cmd_start(msg)

    # ── Main message handler ──────────────────────────────────────────────

    async def _handle_message(self, msg: dict) -> None:
        chat_id = msg["chat_id"]
        text = msg.get("text", "").strip()
        if not text:
            return

        self._modes.get(str(chat_id), "command")
        context_str = self._history.context_string(str(chat_id))
        full_prompt = f"{context_str}\nUser: {text}" if context_str else text

        self._history.add(str(chat_id), "user", text)

        # Send typing indicator
        await self._connector._call("sendChatAction", {"chat_id": chat_id, "action": "typing"})

        try:
            result = await self._orchestrator.handle_request(full_prompt)
            response = result.result or "No response."
            self._history.add(str(chat_id), "assistant", response[:500])

            # Add confidence + agent footer
            confidence_bar = "▓" * int(result.confidence * 10) + "░" * (10 - int(result.confidence * 10))
            footer = (
                f"\n\n<code>{confidence_bar} {result.confidence:.0%}</code> "
                f"<i>via {result.agent_id}</i>"
            )
            if result.requires_human_review:
                footer += "\n⚠️ <i>Requires human review</i>"

            await self._connector.send_message(chat_id, response + footer)

        except Exception as exc:
            logger.error("TelegramBot handle_message error: %s", exc)
            await self._connector.send_message(chat_id, f"❌ Error: {exc}")

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self) -> None:
        logger.info("TelegramBot starting long-poll loop")
        await self._connector.set_commands([
            ("start",  "Welcome and capabilities"),
            ("status", "System health check"),
            ("mode",   "Switch operating mode"),
            ("memory", "View memory snapshot"),
            ("clear",  "Clear conversation history"),
            ("help",   "Show help"),
        ])
        await self._connector.start_polling(stop_event=self._stop_event)

    def stop(self) -> None:
        self._stop_event.set()
        self._connector.stop_polling()
