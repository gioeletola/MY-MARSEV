"""
Telegram bidirectional integration — real Bot API connector via httpx.

Requires:
  TELEGRAM_BOT_TOKEN = "123456:ABC..."   in .env or secrets
  TELEGRAM_ALLOWED_CHAT_IDS = "12345,67890"  (comma-separated, optional whitelist)

Features:
  - send_message / send_markdown / send_file
  - Long-polling update loop (async)
  - Callback routing: register handlers by command prefix or keyword
  - Auto-splits messages > 4096 chars
  - Inline keyboard helper
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)

_BASE = "https://api.telegram.org/bot{token}/{method}"
_MAX_MSG_LEN = 4096
_POLL_TIMEOUT = 30

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class TelegramMessage:
    chat_id: int
    text: str
    message_id: int
    from_user: dict = field(default_factory=dict)
    date: int = 0
    is_command: bool = False
    command: str = ""
    args: str = ""


class TelegramIntegration(BaseIntegration):
    """
    Bidirectional Telegram Bot connector.
    Sends messages and receives/routes incoming messages via long-polling.
    """

    integration_id = "telegram"
    name = "Telegram Integration"

    def __init__(self) -> None:
        super().__init__()
        self._token: str = ""
        self._allowed_ids: set[int] = set()
        self._offset: int = 0
        self._handlers: list[tuple[str, MessageHandler]] = []
        self._fallback_handler: MessageHandler | None = None
        self._running = False
        self._http: httpx.AsyncClient | None = None

    # ── BaseIntegration interface ──────────────────────────────────────────

    def connect(self, config: IntegrationConfig) -> bool:
        self._token = (
            config.credentials.get("bot_token")
            or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        )
        raw_ids = config.settings.get("allowed_chat_ids", "") or os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
        self._allowed_ids = {int(x.strip()) for x in raw_ids.split(",") if x.strip().isdigit()}
        if not self._token:
            logger.warning("TelegramIntegration: no bot token — disabled")
            self._status = IntegrationStatus.DISCONNECTED
            return False
        self._http = httpx.AsyncClient(timeout=60.0)
        self._status = IntegrationStatus.CONNECTED
        logger.info("TelegramIntegration connected (token present, %d allowed IDs)", len(self._allowed_ids))
        return True

    def disconnect(self) -> bool:
        self._running = False
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        if not self._token:
            return False
        import asyncio as _asyncio
        try:
            loop = _asyncio.new_event_loop()
            result = loop.run_until_complete(self._get_me())
            loop.close()
            return result is not None
        except Exception:
            return False

    def fetch(self, resource: str, params: dict) -> dict:
        """Telegram is push-only via Bot API; incoming updates arrive via long-poll loop."""
        return {}

    def push(self, resource: str, data: dict) -> dict:
        if resource == "send_message":
            import asyncio as _asyncio
            try:
                loop = _asyncio.new_event_loop()
                loop.run_until_complete(self.send_message(data["chat_id"], data["text"]))
                loop.close()
                return {"ok": True}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
        return {}

    # ── Sending ───────────────────────────────────────────────────────────

    async def send_message(self, chat_id: int | str, text: str) -> bool:
        if not self._token or not self._http:
            logger.debug("TelegramIntegration: not connected")
            return False
        for chunk in self._split(text):
            try:
                resp = await self._call("sendMessage", {
                    "chat_id": chat_id, "text": chunk, "parse_mode": "HTML"
                })
                if not resp.get("ok"):
                    logger.warning("Telegram sendMessage failed: %s", resp)
                    return False
            except Exception as exc:
                logger.error("Telegram send error: %s", exc)
                return False
        return True

    async def send_markdown(self, chat_id: int | str, text: str) -> bool:
        if not self._token or not self._http:
            return False
        for chunk in self._split(text):
            try:
                await self._call("sendMessage", {
                    "chat_id": chat_id, "text": chunk, "parse_mode": "MarkdownV2"
                })
            except Exception as exc:
                logger.error("Telegram send_markdown error: %s", exc)
                return False
        return True

    async def send_file(self, chat_id: int | str, file_path: str, caption: str = "") -> bool:
        if not self._token or not self._http:
            return False
        url = _BASE.format(token=self._token, method="sendDocument")
        try:
            with open(file_path, "rb") as f:
                resp = await self._http.post(url, data={"chat_id": chat_id, "caption": caption},
                                              files={"document": f})
            data = resp.json()
            return data.get("ok", False)
        except Exception as exc:
            logger.error("Telegram send_file error: %s", exc)
            return False

    async def send_inline_keyboard(self, chat_id: int | str, text: str,
                                    buttons: list[list[dict]]) -> bool:
        """buttons: [[{"text":"Yes","callback_data":"yes"}, ...], ...]"""
        if not self._token or not self._http:
            return False
        markup = json.dumps({"inline_keyboard": buttons})
        try:
            resp = await self._call("sendMessage", {
                "chat_id": chat_id, "text": text,
                "reply_markup": markup, "parse_mode": "HTML"
            })
            return resp.get("ok", False)
        except Exception as exc:
            logger.error("Telegram inline keyboard error: %s", exc)
            return False

    # ── Receiving (long-poll) ─────────────────────────────────────────────

    def on_command(self, command: str, handler: MessageHandler) -> None:
        """Register handler for /command messages."""
        self._handlers.append((command.lstrip("/"), handler))

    def on_message(self, handler: MessageHandler) -> None:
        """Fallback handler for non-command messages."""
        self._fallback_handler = handler

    async def start_polling(self, stop_event: asyncio.Event | None = None) -> None:
        if not self._token:
            logger.warning("TelegramIntegration: no token, polling not started")
            return
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=_POLL_TIMEOUT + 5.0)
        self._running = True
        logger.info("TelegramIntegration: long-poll loop started")
        while self._running:
            if stop_event and stop_event.is_set():
                break
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._dispatch(update)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Telegram polling error: %s", exc)
                await asyncio.sleep(5.0)

    def stop_polling(self) -> None:
        self._running = False

    # ── Internal ──────────────────────────────────────────────────────────

    async def _get_me(self) -> dict | None:
        try:
            resp = await self._call("getMe", {})
            return resp.get("result")
        except Exception:
            return None

    async def _get_updates(self) -> list[dict]:
        resp = await self._call("getUpdates", {
            "offset": self._offset,
            "timeout": _POLL_TIMEOUT,
            "allowed_updates": ["message", "callback_query"],
        })
        updates = resp.get("result", [])
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates

    async def _dispatch(self, update: dict) -> None:
        msg_data = update.get("message") or update.get("callback_query", {}).get("message")
        if not msg_data:
            return
        chat_id = msg_data.get("chat", {}).get("id", 0)
        if self._allowed_ids and chat_id not in self._allowed_ids:
            logger.debug("Telegram: ignoring unauthorised chat_id %d", chat_id)
            return
        text = msg_data.get("text", "")
        msg = TelegramMessage(
            chat_id=chat_id,
            text=text,
            message_id=msg_data.get("message_id", 0),
            from_user=msg_data.get("from", {}),
            date=msg_data.get("date", 0),
            is_command=text.startswith("/"),
        )
        if msg.is_command:
            parts = text.lstrip("/").split(None, 1)
            msg.command = parts[0].split("@")[0].lower()
            msg.args = parts[1] if len(parts) > 1 else ""
            for cmd, handler in self._handlers:
                if cmd == msg.command:
                    await handler(msg.__dict__)
                    return
        if self._fallback_handler:
            await self._fallback_handler(msg.__dict__)

    async def _call(self, method: str, data: dict) -> dict:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=60.0)
        url = _BASE.format(token=self._token, method=method)
        resp = await self._http.post(url, json=data)
        return resp.json()

    @staticmethod
    def _split(text: str) -> list[str]:
        if len(text) <= _MAX_MSG_LEN:
            return [text]
        chunks = []
        while text:
            chunks.append(text[:_MAX_MSG_LEN])
            text = text[_MAX_MSG_LEN:]
        return chunks

    # ── Bot commands helper ───────────────────────────────────────────────

    async def set_commands(self, commands: list[tuple[str, str]]) -> bool:
        """Set the bot's command list shown in Telegram UI."""
        payload = [{"command": c, "description": d} for c, d in commands]
        resp = await self._call("setMyCommands", {"commands": payload})
        return resp.get("ok", False)
