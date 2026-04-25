"""Screenshot Organizer — index and search screenshots."""
from __future__ import annotations

import json
import logging
import pathlib
import time
import uuid

from sovereign.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)
_INDEX_FILE = pathlib.Path("data/memory/screenshots.json")


class ScreenshotTool(BaseTool):
    tool_id = "screenshot_tool"
    name = "Screenshot Organizer"
    description = "Register, search, and retrieve screenshots by description or tag."
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["register", "search", "list", "get"]},
            "file_path": {"type": "string"},
            "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "query": {"type": "string"},
            "screenshot_id": {"type": "string"},
            "limit": {"type": "integer", "default": 20},
        },
        "required": ["action"],
    }

    def _load(self) -> list[dict]:
        if not _INDEX_FILE.exists():
            return []
        try:
            return json.loads(_INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self, data: list[dict]) -> None:
        _INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        _INDEX_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def execute(self, params: dict, context: dict) -> dict:
        try:
            action = params["action"]
            screenshots = self._load()
            if action == "register":
                entry = {"id": str(uuid.uuid4())[:8], "file_path": params.get("file_path", ""), "description": params.get("description", ""), "tags": params.get("tags", []), "ts": time.time()}
                screenshots.append(entry)
                self._save(screenshots)
                return {"result": entry, "error": None}
            elif action == "search":
                query = params.get("query", "").lower()
                results = [s for s in screenshots if query in s.get("description", "").lower() or any(query in t.lower() for t in s.get("tags", []))]
                return {"result": results, "error": None}
            elif action == "list":
                return {"result": screenshots[-params.get("limit", 20):], "error": None}
            elif action == "get":
                sid = params.get("screenshot_id")
                found = next((s for s in screenshots if s["id"] == sid), None)
                return {"result": found, "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}
