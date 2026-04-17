"""Unified notification dispatch — system tray, email, Telegram, console."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

_DATA_FILE = Path("data/ledger/notifications.jsonl")


class NotificationLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationChannel(str, Enum):
    SYSTEM = "system"
    EMAIL = "email"
    TELEGRAM = "telegram"
    CONSOLE = "console"


@dataclass
class Notification:
    notification_id: str
    title: str
    body: str
    level: NotificationLevel = NotificationLevel.INFO
    channels: list[str] = field(default_factory=lambda: ["system"])
    source_agent: str = ""
    read: bool = False
    sent_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


Handler = Callable[[Notification], Awaitable[None]]


class NotificationService:
    """
    Dispatches notifications to registered channel handlers.
    Persists all notifications to JSONL for audit.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}
        self._history: list[Notification] = []
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_handler(NotificationChannel.CONSOLE, self._console_handler)

    def register_handler(self, channel: NotificationChannel | str, handler: Handler) -> None:
        ch = str(channel)
        self._handlers.setdefault(ch, []).append(handler)

    async def send(
        self,
        title: str,
        body: str,
        level: NotificationLevel = NotificationLevel.INFO,
        channels: list[str] | None = None,
        source_agent: str = "",
        metadata: dict | None = None,
    ) -> Notification:
        import uuid
        notif = Notification(
            notification_id=str(uuid.uuid4())[:8],
            title=title,
            body=body,
            level=level,
            channels=channels or [NotificationChannel.CONSOLE],
            source_agent=source_agent,
            metadata=metadata or {},
        )
        self._history.append(notif)
        self._persist(notif)

        for ch in notif.channels:
            for handler in self._handlers.get(ch, []):
                try:
                    await handler(notif)
                except Exception as exc:
                    logger.error("Notification handler %s failed: %s", ch, exc)

        return notif

    async def broadcast(self, title: str, body: str, level: NotificationLevel = NotificationLevel.INFO) -> None:
        await self.send(title, body, level, channels=list(self._handlers.keys()))

    def _persist(self, notif: Notification) -> None:
        try:
            with open(_DATA_FILE, "a") as f:
                f.write(json.dumps(notif.__dict__) + "\n")
        except Exception as exc:
            logger.warning("Failed to persist notification: %s", exc)

    async def _console_handler(self, notif: Notification) -> None:
        icons = {
            NotificationLevel.INFO: "ℹ",
            NotificationLevel.SUCCESS: "✓",
            NotificationLevel.WARNING: "⚠",
            NotificationLevel.CRITICAL: "✖",
        }
        icon = icons.get(notif.level, "•")
        logger.info("[%s] %s %s — %s", notif.level.upper(), icon, notif.title, notif.body)

    def unread(self) -> list[Notification]:
        return [n for n in self._history if not n.read]

    def mark_read(self, notification_id: str) -> bool:
        for n in self._history:
            if n.notification_id == notification_id:
                n.read = True
                return True
        return False

    def recent(self, n: int = 20) -> list[Notification]:
        return sorted(self._history, key=lambda x: x.sent_at, reverse=True)[:n]

    def by_level(self, level: NotificationLevel) -> list[Notification]:
        return [n for n in self._history if n.level == level]

    def critical_count(self) -> int:
        return sum(1 for n in self._history if n.level == NotificationLevel.CRITICAL and not n.read)
