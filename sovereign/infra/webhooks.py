"""Webhook system — receive and dispatch webhook events."""
from __future__ import annotations

import json
import logging
import pathlib
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Callable, Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/ledger/webhooks.jsonl")


@dataclass
class WebhookEvent:
    event_id: str
    source: str
    event_type: str
    payload: dict
    received_at: float = field(default_factory=time.time)
    processed: bool = False
    processing_error: str = ""


@dataclass
class _HandlerRecord:
    handler_id: str
    source: str
    event_type: str
    handler: Callable


class WebhookRouter:
    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._handlers: dict[str, _HandlerRecord] = {}
        self._events: list[WebhookEvent] = []
        self._stats = {"total": 0, "processed": 0, "failed": 0}

    def register(self, source: str, event_type: str, handler: Callable) -> str:
        handler_id = str(uuid.uuid4())[:8]
        self._handlers[handler_id] = _HandlerRecord(handler_id, source, event_type, handler)
        logger.debug("Webhooks: registered handler %s for %s/%s", handler_id, source, event_type)
        return handler_id

    def unregister(self, handler_id: str) -> bool:
        if handler_id in self._handlers:
            del self._handlers[handler_id]
            return True
        return False

    async def receive(self, source: str, event_type: str, payload: dict) -> WebhookEvent:
        event = WebhookEvent(
            event_id=str(uuid.uuid4())[:8],
            source=source,
            event_type=event_type,
            payload=payload,
        )
        self._events.append(event)
        self._stats["total"] += 1
        await self.dispatch(event)
        self._append(event)
        return event

    async def dispatch(self, event: WebhookEvent) -> list[bool]:
        handlers = self._match_handlers(event.source, event.event_type)
        if not handlers:
            logger.debug("Webhooks: no handlers for %s/%s", event.source, event.event_type)
            return []
        results = []
        for rec in handlers:
            try:
                result = rec.handler(event)
                if hasattr(result, "__await__"):
                    result = await result
                results.append(bool(result))
                event.processed = True
                self._stats["processed"] += 1
            except Exception as exc:
                event.processing_error = str(exc)
                self._stats["failed"] += 1
                results.append(False)
                logger.error("Webhook handler %s error: %s", rec.handler_id, exc)
        return results

    def _match_handlers(self, source: str, event_type: str) -> list[_HandlerRecord]:
        matched = []
        for rec in self._handlers.values():
            source_match = rec.source in (source, "*")
            type_match = rec.event_type in (event_type, "*")
            if source_match and type_match:
                matched.append(rec)
        return matched

    def pending_events(self) -> list[WebhookEvent]:
        return [e for e in self._events if not e.processed]

    def event_history(self, limit: int = 50) -> list[WebhookEvent]:
        return self._events[-limit:]

    def stats(self) -> dict[str, Any]:
        return {**self._stats, "pending": len(self.pending_events())}

    def _append(self, event: WebhookEvent) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event)) + "\n")
        except Exception as exc:
            logger.error("Webhooks append failed: %s", exc)
