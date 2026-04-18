"""Bookmark Intelligence — save and retrieve intelligent bookmarks."""
from __future__ import annotations
import json
import logging
import pathlib
import time
import uuid
from sovereign.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)
_BOOKMARKS_FILE = pathlib.Path("data/memory/bookmarks.json")


class BookmarkTool(BaseTool):
    tool_id = "bookmark_tool"
    name = "Bookmark Intelligence"
    description = "Save, search, and manage intelligent bookmarks with tags."
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["save", "get", "search", "list", "delete"]},
            "url": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "bookmark_id": {"type": "string"},
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 20},
            "tag": {"type": "string"},
        },
        "required": ["action"],
    }

    def _load(self) -> list[dict]:
        if not _BOOKMARKS_FILE.exists():
            return []
        try:
            return json.loads(_BOOKMARKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, data: list[dict]) -> None:
        _BOOKMARKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _BOOKMARKS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def execute(self, params: dict, context: dict) -> dict:
        try:
            action = params["action"]
            bookmarks = self._load()
            if action == "save":
                entry = {"id": str(uuid.uuid4())[:8], "url": params.get("url", ""), "title": params.get("title", ""), "description": params.get("description", ""), "tags": params.get("tags", []), "saved_at": time.time()}
                bookmarks.append(entry)
                self._save(bookmarks)
                return {"result": entry, "error": None}
            elif action == "get":
                bid = params.get("bookmark_id")
                found = next((b for b in bookmarks if b["id"] == bid), None)
                return {"result": found, "error": None}
            elif action == "search":
                query = params.get("query", "").lower()
                results = [b for b in bookmarks if query in b.get("title", "").lower() or query in b.get("description", "").lower() or any(query in t.lower() for t in b.get("tags", []))]
                return {"result": results, "error": None}
            elif action == "list":
                limit = params.get("limit", 20)
                tag = params.get("tag")
                results = bookmarks if not tag else [b for b in bookmarks if tag in b.get("tags", [])]
                return {"result": results[-limit:], "error": None}
            elif action == "delete":
                bid = params.get("bookmark_id")
                bookmarks = [b for b in bookmarks if b["id"] != bid]
                self._save(bookmarks)
                return {"result": {"deleted": bid}, "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}
