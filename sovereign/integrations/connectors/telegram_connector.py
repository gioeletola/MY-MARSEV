"""
Telegram connector — polls messages and commands from a Telegram bot via Bot API.
Auth: bot token from vault or TELEGRAM_BOT_TOKEN env var.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase,
    ConnectorHealth,
    ConnectorStatus,
    SyncResult,
)

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramConnector(ConnectorBase):
    connector_id = "telegram"
    connector_name = "Telegram Bot"
    connector_description = "Polls Telegram bot messages and commands; supports sending replies and media."
    connector_status = ConnectorStatus.CONNECTED
    requires_oauth = False  # Bot token auth

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._token = (
            self._config.get("token")
            or os.getenv("TELEGRAM_BOT_TOKEN")
            or ""
        )
        self._default_chat_id: int | str | None = (
            self._config.get("chat_id")
            or os.getenv("TELEGRAM_CHAT_ID")
            or None
        )
        self._allowed_chat_ids: list[int] = self._config.get("allowed_chat_ids", [])
        self._offset: int = 0
        self._messages: list[dict] = []

    def _base_url(self) -> str:
        return _API_BASE.format(token=self._token)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        if not self._token:
            self._logger.warning("TelegramConnector: no bot token configured")
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base_url()}/getMe")
                data = resp.json()
                if data.get("ok"):
                    bot = data["result"]
                    self._logger.info("TelegramConnector: connected as @%s", bot.get("username"))
                    self.connector_status = ConnectorStatus.CONNECTED
                    return True
                self._logger.warning("TelegramConnector: auth failed: %s", data.get("description"))
        except Exception as exc:
            self._logger.error("TelegramConnector: connect error: %s", exc)
        return False

    async def disconnect(self) -> None:
        self._messages = []
        self._offset = 0
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if not self._token:
            return SyncResult(connector_id=self.connector_id, success=False, errors=["No token"])
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url()}/getUpdates",
                    params={"offset": self._offset, "limit": 100, "timeout": 0},
                )
                data = resp.json()
                if not data.get("ok"):
                    return SyncResult(
                        connector_id=self.connector_id,
                        success=False,
                        errors=[data.get("description", "unknown error")],
                    )

                updates = data.get("result", [])
                messages: list[dict] = []
                for update in updates:
                    self._offset = update["update_id"] + 1
                    msg = update.get("message") or update.get("edited_message")
                    if msg:
                        chat_id = msg.get("chat", {}).get("id")
                        if self._allowed_chat_ids and chat_id not in self._allowed_chat_ids:
                            continue
                        messages.append(msg)

                self._messages.extend(messages)
                self.connector_status = ConnectorStatus.CONNECTED
                result = SyncResult(
                    connector_id=self.connector_id,
                    success=True,
                    records_synced=len(messages),
                )
                self._mark_sync(result)
                return result
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=len(self._messages),
            metadata={
                "token_configured": bool(self._token),
                "offset": self._offset,
                "allowed_chats": len(self._allowed_chat_ids),
            },
        )

    # ------------------------------------------------------------------
    # Domain methods
    # ------------------------------------------------------------------

    async def send_message(
        self,
        text: str,
        chat_id: int | str | None = None,
        parse_mode: str = "HTML",
    ) -> dict:
        """
        Send a text message to `chat_id` (defaults to TELEGRAM_CHAT_ID).
        Returns the Telegram Message object dict or raises on error.
        """
        if not self._token:
            raise RuntimeError("TelegramConnector: no bot token configured")
        target = chat_id or self._default_chat_id
        if target is None:
            raise RuntimeError("TelegramConnector: no chat_id provided and TELEGRAM_CHAT_ID not set")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._base_url()}/sendMessage",
                    json={"chat_id": target, "text": text, "parse_mode": parse_mode},
                )
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", {})
                raise RuntimeError(f"TelegramConnector: sendMessage failed: {data.get('description')}")
        except RuntimeError:
            raise
        except Exception as exc:
            self._logger.error("TelegramConnector: sendMessage error: %s", exc)
            raise

    async def send_photo(
        self,
        photo_url: str,
        caption: str = "",
        chat_id: int | str | None = None,
    ) -> dict:
        """
        Send a photo (by URL) to `chat_id`.
        Returns the Telegram Message object dict.
        """
        if not self._token:
            raise RuntimeError("TelegramConnector: no bot token configured")
        target = chat_id or self._default_chat_id
        if target is None:
            raise RuntimeError("TelegramConnector: no chat_id provided and TELEGRAM_CHAT_ID not set")
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url()}/sendPhoto",
                json={"chat_id": target, "photo": photo_url, "caption": caption},
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("result", {})
            raise RuntimeError(f"TelegramConnector: sendPhoto failed: {data.get('description')}")

    async def get_updates(self, offset: int = 0, limit: int = 10) -> list[dict]:
        """
        Fetch up to `limit` pending updates starting from `offset`.
        Returns a list of Telegram Update objects.
        """
        if not self._token:
            return []
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url()}/getUpdates",
                params={"offset": offset, "limit": limit, "timeout": 0},
            )
            data = resp.json()
            return data.get("result", []) if data.get("ok") else []

    async def get_chat_info(self, chat_id: int | str | None = None) -> dict:
        """
        Return info about the given chat (defaults to TELEGRAM_CHAT_ID).
        """
        if not self._token:
            raise RuntimeError("TelegramConnector: no bot token configured")
        target = chat_id or self._default_chat_id
        if target is None:
            raise RuntimeError("TelegramConnector: no chat_id provided and TELEGRAM_CHAT_ID not set")
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._base_url()}/getChat",
                params={"chat_id": target},
            )
            data = resp.json()
            if data.get("ok"):
                return data.get("result", {})
            raise RuntimeError(f"TelegramConnector: getChat failed: {data.get('description')}")

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def get_messages(self) -> list[dict]:
        return self._messages

    def clear_messages(self) -> None:
        self._messages = []
