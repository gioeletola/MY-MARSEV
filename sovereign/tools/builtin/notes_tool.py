"""
Notes tool — create and retrieve notes, persisted to data/memory/notes.json.
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

_NOTES_FILE = pathlib.Path("data/memory/notes.json")


class NotesTool(BaseTool):
    """
    Create, retrieve, search, and manage text notes.

    Notes are persisted as a JSON list in data/memory/notes.json.
    Each note: {id, title, content, tags, created_at, updated_at}.
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="notes_tool",
            description="Create and retrieve notes",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "get", "search", "list", "update", "delete"],
                        "description": (
                            "Notes operation: 'create' — new note; 'get' — fetch by ID; "
                            "'search' — full-text search; 'list' — all notes; "
                            "'update' — update content; 'delete' — remove note."
                        ),
                    },
                    "title": {
                        "type": "string",
                        "description": "Note title (required for create).",
                    },
                    "content": {
                        "type": "string",
                        "description": "Note body text (required for create/update).",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tag strings for create.",
                    },
                    "note_id": {
                        "type": "string",
                        "description": "Note UUID (required for get, update, delete).",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search string (required for search).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of notes to return for list (default 20).",
                        "default": 20,
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str,
        title: str = "",
        content: str = "",
        tags: list[str] | None = None,
        note_id: str = "",
        query: str = "",
        limit: int = 20,
        **_: Any,
    ) -> Any:
        """Execute a notes operation."""
        try:
            notes = self._load()
            if action == "create":
                if not title:
                    return {"error": "title is required for create"}
                return self._create(notes, title, content, tags or [])
            if action == "get":
                if not note_id:
                    return {"error": "note_id is required for get"}
                return self._get(notes, note_id)
            if action == "search":
                if not query:
                    return {"error": "query is required for search"}
                return self._search(notes, query)
            if action == "list":
                return self._list(notes, max(1, limit))
            if action == "update":
                if not note_id:
                    return {"error": "note_id is required for update"}
                return self._update(notes, note_id, content)
            if action == "delete":
                if not note_id:
                    return {"error": "note_id is required for delete"}
                return self._delete(notes, note_id)
            return {"error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.error("NotesTool error action=%s: %s", action, exc)
            return {"result": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> list[dict[str, Any]]:
        path = _NOTES_FILE
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, notes: list[dict[str, Any]]) -> None:
        _NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        _NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _create(
        self,
        notes: list[dict[str, Any]],
        title: str,
        content: str,
        tags: list[str],
    ) -> dict[str, Any]:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        note: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "title": title,
            "content": content,
            "tags": tags,
            "created_at": now,
            "updated_at": now,
        }
        notes.append(note)
        self._save(notes)
        logger.info("NotesTool.create id=%s title=%r", note["id"], title)
        return {"created": True, "note": note}

    def _get(self, notes: list[dict[str, Any]], note_id: str) -> dict[str, Any]:
        for note in notes:
            if note.get("id") == note_id:
                return {"note": note}
        return {"error": f"Note not found: {note_id}"}

    def _search(self, notes: list[dict[str, Any]], query: str) -> dict[str, Any]:
        q = query.lower()
        matches = [
            n for n in notes
            if q in n.get("title", "").lower()
            or q in n.get("content", "").lower()
            or any(q in t.lower() for t in n.get("tags", []))
        ]
        return {"query": query, "count": len(matches), "notes": matches}

    def _list(self, notes: list[dict[str, Any]], limit: int) -> dict[str, Any]:
        recent = sorted(notes, key=lambda n: n.get("updated_at", ""), reverse=True)[:limit]
        return {"count": len(recent), "notes": recent}

    def _update(
        self, notes: list[dict[str, Any]], note_id: str, content: str
    ) -> dict[str, Any]:
        for note in notes:
            if note.get("id") == note_id:
                note["content"] = content
                note["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                self._save(notes)
                return {"updated": True, "note": note}
        return {"error": f"Note not found: {note_id}"}

    def _delete(self, notes: list[dict[str, Any]], note_id: str) -> dict[str, Any]:
        original_len = len(notes)
        remaining = [n for n in notes if n.get("id") != note_id]
        if len(remaining) == original_len:
            return {"error": f"Note not found: {note_id}"}
        self._save(remaining)
        return {"deleted": True, "note_id": note_id}
