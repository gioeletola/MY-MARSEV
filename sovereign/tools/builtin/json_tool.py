"""
JSON tool — parse, format, validate, query, diff, and merge JSON.

No external dependencies — uses stdlib json only.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)


def _query_dot_path(data: Any, path: str) -> Any:
    """
    Navigate a nested structure using dot-notation path.

    Supports dict keys and list indices (e.g. "user.addresses.0.city").
    Raises KeyError / IndexError / TypeError on invalid path.
    """
    if not path:
        return data
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(f"Key '{part}' not found")
            current = current[part]
        elif isinstance(current, list):
            try:
                idx = int(part)
            except ValueError:
                raise KeyError(f"Cannot index list with non-integer key '{part}'")
            current = current[idx]
        else:
            raise TypeError(f"Cannot traverse into {type(current).__name__} with key '{part}'")
    return current


def _diff_objects(a: Any, b: Any, path: str = "") -> list[dict[str, Any]]:
    """Recursively diff two JSON-compatible objects. Returns list of change dicts."""
    diffs: list[dict[str, Any]] = []

    if type(a) != type(b):  # noqa: E721
        diffs.append({"path": path or ".", "type": "changed", "from": a, "to": b})
        return diffs

    if isinstance(a, dict):
        all_keys = set(a) | set(b)
        for key in sorted(all_keys):
            child_path = f"{path}.{key}" if path else key
            if key not in a:
                diffs.append({"path": child_path, "type": "added", "value": b[key]})
            elif key not in b:
                diffs.append({"path": child_path, "type": "removed", "value": a[key]})
            else:
                diffs.extend(_diff_objects(a[key], b[key], child_path))
    elif isinstance(a, list):
        max_len = max(len(a), len(b))
        for i in range(max_len):
            child_path = f"{path}[{i}]"
            if i >= len(a):
                diffs.append({"path": child_path, "type": "added", "value": b[i]})
            elif i >= len(b):
                diffs.append({"path": child_path, "type": "removed", "value": a[i]})
            else:
                diffs.extend(_diff_objects(a[i], b[i], child_path))
    else:
        if a != b:
            diffs.append({"path": path or ".", "type": "changed", "from": a, "to": b})

    return diffs


def _deep_merge(base: Any, override: Any) -> Any:
    """Deep-merge two dicts. Override values win; nested dicts are merged recursively."""
    if isinstance(base, dict) and isinstance(override, dict):
        result = dict(base)
        for key, val in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(val, dict):
                result[key] = _deep_merge(result[key], val)
            else:
                result[key] = val
        return result
    # For non-dict types, override wins
    return override


class JsonTool(BaseTool):
    """
    JSON utility: format, minify, validate, query, diff, and merge JSON data.
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="json_tool",
            description=(
                "JSON utility: format (pretty-print), minify, validate, query with "
                "dot-notation path, diff two JSON objects, or deep-merge two JSON dicts."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["format", "minify", "validate", "query", "diff", "merge"],
                        "description": (
                            "'format' — pretty-print JSON string; "
                            "'minify' — compact JSON string; "
                            "'validate' — check if JSON is valid; "
                            "'query' — dot-path query on parsed JSON; "
                            "'diff' — structural diff between two JSON values; "
                            "'merge' — deep-merge two JSON dicts."
                        ),
                    },
                    "json_text": {
                        "type": "string",
                        "description": "JSON string input (used by format, minify, validate, query).",
                    },
                    "json_a": {
                        "type": "string",
                        "description": "First JSON string (used by diff, merge).",
                    },
                    "json_b": {
                        "type": "string",
                        "description": "Second JSON string (used by diff, merge).",
                    },
                    "path": {
                        "type": "string",
                        "description": "Dot-notation path for query action (e.g. 'user.address.city').",
                    },
                    "indent": {
                        "type": "integer",
                        "description": "Indentation spaces for format action. Default: 2.",
                        "default": 2,
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str,
        json_text: str = "",
        json_a: str = "",
        json_b: str = "",
        path: str = "",
        indent: int = 2,
        **_: Any,
    ) -> Any:
        """Execute a JSON operation."""
        try:
            if action == "format":
                if not json_text:
                    return {"error": "json_text is required for format"}
                parsed = json.loads(json_text)
                return {
                    "action": "format",
                    "result": json.dumps(parsed, indent=max(1, indent), ensure_ascii=False),
                    "error": None,
                }

            if action == "minify":
                if not json_text:
                    return {"error": "json_text is required for minify"}
                parsed = json.loads(json_text)
                return {
                    "action": "minify",
                    "result": json.dumps(parsed, separators=(",", ":"), ensure_ascii=False),
                    "error": None,
                }

            if action == "validate":
                if not json_text:
                    return {"valid": False, "error": "json_text is required"}
                try:
                    parsed = json.loads(json_text)
                    return {
                        "action": "validate",
                        "valid": True,
                        "type": type(parsed).__name__,
                        "error": None,
                    }
                except json.JSONDecodeError as exc:
                    return {
                        "action": "validate",
                        "valid": False,
                        "error": str(exc),
                    }

            if action == "query":
                if not json_text:
                    return {"error": "json_text is required for query"}
                if not path:
                    return {"error": "path is required for query"}
                parsed = json.loads(json_text)
                try:
                    value = _query_dot_path(parsed, path)
                    return {
                        "action": "query",
                        "path": path,
                        "result": value,
                        "error": None,
                    }
                except (KeyError, IndexError, TypeError) as exc:
                    return {"action": "query", "path": path, "result": None, "error": str(exc)}

            if action == "diff":
                if not json_a or not json_b:
                    return {"error": "json_a and json_b are required for diff"}
                obj_a = json.loads(json_a)
                obj_b = json.loads(json_b)
                diffs = _diff_objects(obj_a, obj_b)
                added = sum(1 for d in diffs if d["type"] == "added")
                removed = sum(1 for d in diffs if d["type"] == "removed")
                changed = sum(1 for d in diffs if d["type"] == "changed")
                return {
                    "action": "diff",
                    "differences": diffs,
                    "summary": {"added": added, "removed": removed, "changed": changed},
                    "identical": len(diffs) == 0,
                    "error": None,
                }

            if action == "merge":
                if not json_a or not json_b:
                    return {"error": "json_a and json_b are required for merge"}
                obj_a = json.loads(json_a)
                obj_b = json.loads(json_b)
                if not isinstance(obj_a, dict) or not isinstance(obj_b, dict):
                    return {"error": "Both json_a and json_b must be JSON objects (dicts) for merge"}
                merged = _deep_merge(obj_a, obj_b)
                return {
                    "action": "merge",
                    "result": merged,
                    "error": None,
                }

            return {"error": f"Unknown action: {action}"}

        except json.JSONDecodeError as exc:
            logger.error("JsonTool JSON parse error action=%s: %s", action, exc)
            return {"result": None, "error": f"JSON parse error: {exc}"}
        except Exception as exc:
            logger.error("JsonTool error action=%s: %s", action, exc)
            return {"result": None, "error": str(exc)}
