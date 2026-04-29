"""Diff Tool — compare text blocks, JSON objects, or file snapshots."""
from __future__ import annotations

import difflib
import json
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class DiffTool(BaseTool):
    """Compare two texts or JSON objects and return a unified diff or structured delta."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="diff_tool",
            description="Compare two text blocks or JSON objects and produce a unified diff or structured delta.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["text_diff", "json_diff", "word_diff", "similarity"],
                        "description": "Operation: text_diff | json_diff | word_diff | similarity",
                    },
                    "original": {"type": "string", "description": "Original text or JSON string"},
                    "modified": {"type": "string", "description": "Modified text or JSON string"},
                    "context_lines": {"type": "integer", "description": "Lines of context (default 3)"},
                },
                "required": ["action", "original", "modified"],
            },
        )

    async def execute(
        self,
        action: str,
        original: str = "",
        modified: str = "",
        context_lines: int = 3,
        **_: Any,
    ) -> Any:
        try:
            if action == "text_diff":
                return self._text_diff(original, modified, context_lines)
            if action == "json_diff":
                return self._json_diff(original, modified)
            if action == "word_diff":
                return self._word_diff(original, modified)
            if action == "similarity":
                return self._similarity(original, modified)
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _text_diff(self, a: str, b: str, n: int) -> dict:
        a_lines = a.splitlines(keepends=True)
        b_lines = b.splitlines(keepends=True)
        diff = list(difflib.unified_diff(a_lines, b_lines, fromfile="original", tofile="modified", n=n))
        added = sum(1 for ln in diff if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in diff if ln.startswith("-") and not ln.startswith("---"))
        return {
            "result": "".join(diff) or "(no differences)",
            "added_lines": added,
            "removed_lines": removed,
            "changed": bool(diff),
            "error": None,
        }

    def _json_diff(self, a: str, b: str) -> dict:
        try:
            obj_a = json.loads(a)
            obj_b = json.loads(b)
        except json.JSONDecodeError as exc:
            return {"result": None, "error": f"JSON parse error: {exc}"}
        deltas = self._dict_delta(obj_a, obj_b, "")
        return {"result": deltas, "changed": bool(deltas), "error": None}

    def _dict_delta(self, a: Any, b: Any, path: str) -> list[dict]:
        out: list[dict] = []
        if type(a) is not type(b):
            out.append({"path": path or "root", "type": "type_change", "from": type(a).__name__, "to": type(b).__name__})
            return out
        if isinstance(a, dict):
            for k in sorted(set(a) | set(b)):
                p = f"{path}.{k}" if path else k
                if k not in a:
                    out.append({"path": p, "type": "added", "value": b[k]})
                elif k not in b:
                    out.append({"path": p, "type": "removed", "value": a[k]})
                else:
                    out.extend(self._dict_delta(a[k], b[k], p))
        elif isinstance(a, list):
            if a != b:
                out.append({"path": path or "root", "type": "list_changed", "from_len": len(a), "to_len": len(b)})
        elif a != b:
            out.append({"path": path or "root", "type": "value_changed", "from": a, "to": b})
        return out

    def _word_diff(self, a: str, b: str) -> dict:
        a_words = a.split()
        b_words = b.split()
        matcher = difflib.SequenceMatcher(None, a_words, b_words)
        parts: list[str] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                parts.append(" ".join(a_words[i1:i2]))
            elif tag == "replace":
                parts.append(f"[-{' '.join(a_words[i1:i2])}-]{{+{' '.join(b_words[j1:j2])}+}}")
            elif tag == "delete":
                parts.append(f"[-{' '.join(a_words[i1:i2])}-]")
            elif tag == "insert":
                parts.append(f"{{+{' '.join(b_words[j1:j2])}+}}")
        ratio = matcher.ratio()
        return {"result": " ".join(parts), "similarity": round(ratio, 4), "changed": ratio < 1.0, "error": None}

    def _similarity(self, a: str, b: str) -> dict:
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        return {
            "result": round(ratio, 4),
            "similarity_pct": round(ratio * 100, 1),
            "identical": ratio == 1.0,
            "error": None,
        }
