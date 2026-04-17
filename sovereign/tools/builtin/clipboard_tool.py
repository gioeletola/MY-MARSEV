"""
Clipboard tool — smart clipboard ring buffer persisted to data/memory/clipboard.json.

Maintains a ring buffer of the last 50 clipboard entries.
Each entry: {id, text, label, ts}.
"""
from __future__ import annotations

import json
import logging
import pathlib
import time
import uuid
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)

_CLIPBOARD_FILE = pathlib.Path("data/memory/clipboard.json")
_MAX_SIZE = 50


class ClipboardTool(BaseTool):
    """
    Smart clipboard — store and retrieve text snippets.

    Ring buffer of the last 50 items, persisted to data/memory/clipboard.json.
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="clipboard_tool",
            description="Smart clipboard — store and retrieve text snippets",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["copy", "paste", "list", "clear", "search"],
                        "description": (
                            "'copy' — add text to clipboard; "
                            "'paste' — retrieve item by index (0 = most recent); "
                            "'list' — list recent items; "
                            "'clear' — remove all items; "
                            "'search' — find items matching query."
                        ),
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to copy (required for copy).",
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional label for the clipboard entry.",
                        "default": "",
                    },
                    "index": {
                        "type": "integer",
                        "description": "0-based index into clipboard history for paste (default 0 = most recent).",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of items to return for list (default 10).",
                        "default": 10,
                    },
                    "query": {
                        "type": "string",
                        "description": "Search string for search action.",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str,
        text: str = "",
        label: str = "",
        index: int = 0,
        limit: int = 10,
        query: str = "",
        **_: Any,
    ) -> Any:
        """Execute a clipboard operation."""
        try:
            items = self._load()
            if action == "copy":
                if not text:
                    return {"error": "text is required for copy"}
                return self._copy(items, text, label)
            if action == "paste":
                return self._paste(items, index)
            if action == "list":
                return self._list(items, max(1, limit))
            if action == "clear":
                return self._clear()
            if action == "search":
                if not query:
                    return {"error": "query is required for search"}
                return self._search(items, query)
            return {"error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.error("ClipboardTool error action=%s: %s", action, exc)
            return {"result": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> list[dict[str, Any]]:
        if not _CLIPBOARD_FILE.exists():
            return []
        try:
            return json.loads(_CLIPBOARD_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, items: list[dict[str, Any]]) -> None:
        _CLIPBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CLIPBOARD_FILE.write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _copy(
        self, items: list[dict[str, Any]], text: str, label: str
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "text": text,
            "label": label,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        # Prepend so index 0 is always most recent
        items.insert(0, entry)
        # Enforce ring buffer size
        if len(items) > _MAX_SIZE:
            items = items[:_MAX_SIZE]
        self._save(items)
        logger.debug("ClipboardTool.copy id=%s chars=%d", entry["id"], len(text))
        return {"copied": True, "entry": entry, "buffer_size": len(items)}

    def _paste(self, items: list[dict[str, Any]], index: int) -> dict[str, Any]:
        if not items:
            return {"error": "Clipboard is empty"}
        if index < 0 or index >= len(items):
            return {
                "error": f"Index {index} out of range — clipboard has {len(items)} item(s)"
            }
        return {"entry": items[index]}

    def _list(self, items: list[dict[str, Any]], limit: int) -> dict[str, Any]:
        visible = items[:limit]
        return {"count": len(visible), "total": len(items), "items": visible}

    def _clear(self) -> dict[str, Any]:
        self._save([])
        return {"cleared": True}

    def _search(self, items: list[dict[str, Any]], query: str) -> dict[str, Any]:
        q = query.lower()
        matches = [
            item for item in items
            if q in item.get("text", "").lower()
            or q in item.get("label", "").lower()
        ]
        return {"query": query, "count": len(matches), "items": matches}
