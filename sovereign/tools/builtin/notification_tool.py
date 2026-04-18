"""Notification Tool — send and manage system notifications."""
from __future__ import annotations
import json
import logging
import pathlib
import time
import uuid
from sovereign.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)
_NOTIF_FILE = pathlib.Path("data/memory/notifications.json")


class NotificationTool(BaseTool):
    tool_id = "notification_tool"
    name = "Notification"
    description = "Send and manage system notifications across channels."
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["send", "list", "mark_read", "clear"]},
            "title": {"type": "string"},
            "message": {"type": "string"},
            "level": {"type": "string", "enum": ["info", "warning", "critical", "success"], "default": "info"},
            "channel": {"type": "string", "default": "system"},
            "notification_id": {"type": "string"},
            "limit": {"type": "integer", "default": 20},
            "unread_only": {"type": "boolean", "default": False},
        },
        "required": ["action"],
    }

    def _load(self) -> list[dict]:
        if not _NOTIF_FILE.exists():
            return []
        try:
            return json.loads(_NOTIF_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, data: list[dict]) -> None:
        _NOTIF_FILE.parent.mkdir(parents=True, exist_ok=True)
        _NOTIF_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def execute(self, params: dict, context: dict) -> dict:
        try:
            action = params["action"]
            notifications = self._load()
            if action == "send":
                level = params.get("level", "info")
                channel = params.get("channel", "system")
                notif = {"id": str(uuid.uuid4())[:8], "title": params.get("title", ""), "message": params.get("message", ""), "level": level, "channel": channel, "read": False, "ts": time.time()}
                notifications.append(notif)
                self._save(notifications)
                logger.info("Notification [%s] %s: %s", level, notif["title"], notif["message"])
                if channel == "email":
                    logger.debug("notification_tool.send: email channel stub")
                elif channel == "telegram":
                    logger.debug("notification_tool.send: telegram channel stub")
                return {"result": notif, "error": None}
            elif action == "list":
                limit = params.get("limit", 20)
                unread_only = params.get("unread_only", False)
                results = notifications if not unread_only else [n for n in notifications if not n.get("read")]
                return {"result": results[-limit:], "error": None}
            elif action == "mark_read":
                nid = params.get("notification_id")
                for n in notifications:
                    if n["id"] == nid:
                        n["read"] = True
                self._save(notifications)
                return {"result": {"marked_read": nid}, "error": None}
            elif action == "clear":
                self._save([])
                return {"result": {"cleared": len(notifications)}, "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}
