"""
Regex tool — find, replace, extract, validate, and split using regular expressions.

No external dependencies — uses stdlib re only.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)


def _compile_flags(ignore_case: bool, multiline: bool, dotall: bool) -> int:
    flags = 0
    if ignore_case:
        flags |= re.IGNORECASE
    if multiline:
        flags |= re.MULTILINE
    if dotall:
        flags |= re.DOTALL
    return flags


class RegexTool(BaseTool):
    """
    Regular expression utility: find all matches, replace, extract groups,
    validate, and split text.
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="regex_tool",
            description=(
                "Regex utility: find all matches, replace text, extract named/unnamed "
                "groups, validate if text matches a pattern, or split text by a pattern."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["find_all", "replace", "extract_groups", "validate", "split"],
                        "description": (
                            "'find_all' — list all non-overlapping matches; "
                            "'replace' — substitute pattern matches with replacement; "
                            "'extract_groups' — return named and unnamed capture groups; "
                            "'validate' — check if text fully matches pattern; "
                            "'split' — split text by pattern."
                        ),
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression pattern.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Input text to operate on.",
                    },
                    "replacement": {
                        "type": "string",
                        "description": "Replacement string for replace action (supports backreferences).",
                    },
                    "ignore_case": {
                        "type": "boolean",
                        "description": "Case-insensitive matching. Default: false.",
                        "default": False,
                    },
                    "multiline": {
                        "type": "boolean",
                        "description": "Multiline mode (^ and $ match line boundaries). Default: false.",
                        "default": False,
                    },
                    "dotall": {
                        "type": "boolean",
                        "description": "Dot matches newline. Default: false.",
                        "default": False,
                    },
                    "max_split": {
                        "type": "integer",
                        "description": "Maximum number of splits (0 = unlimited). Default: 0.",
                        "default": 0,
                    },
                },
                "required": ["action", "pattern", "text"],
            },
        )

    async def execute(
        self,
        action: str,
        pattern: str = "",
        text: str = "",
        replacement: str = "",
        ignore_case: bool = False,
        multiline: bool = False,
        dotall: bool = False,
        max_split: int = 0,
        **_: Any,
    ) -> Any:
        """Execute a regex operation."""
        try:
            if not pattern:
                return {"error": "pattern is required"}
            if not isinstance(text, str):
                return {"error": "text must be a string"}

            flags = _compile_flags(ignore_case, multiline, dotall)

            try:
                compiled = re.compile(pattern, flags)
            except re.error as exc:
                return {"error": f"Invalid regex pattern: {exc}"}

            if action == "find_all":
                matches = compiled.findall(text)
                # findall returns strings or tuples depending on groups
                return {
                    "action": "find_all",
                    "matches": [m if isinstance(m, str) else list(m) for m in matches],
                    "count": len(matches),
                    "error": None,
                }

            if action == "replace":
                result = compiled.sub(replacement, text)
                num_subs = len(compiled.findall(text))
                return {
                    "action": "replace",
                    "result": result,
                    "substitutions": num_subs,
                    "error": None,
                }

            if action == "extract_groups":
                all_groups: list[dict[str, Any]] = []
                for match in compiled.finditer(text):
                    entry: dict[str, Any] = {
                        "match": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                        "groups": list(match.groups()),
                        "named_groups": match.groupdict(),
                    }
                    all_groups.append(entry)
                return {
                    "action": "extract_groups",
                    "matches": all_groups,
                    "count": len(all_groups),
                    "error": None,
                }

            if action == "validate":
                match = compiled.fullmatch(text)
                if match:
                    return {
                        "action": "validate",
                        "valid": True,
                        "reason": "Text fully matches the pattern",
                        "groups": list(match.groups()),
                        "named_groups": match.groupdict(),
                        "error": None,
                    }
                # Provide partial match info for a better reason
                partial = compiled.search(text)
                reason = (
                    f"Partial match found at position {partial.start()}" if partial
                    else "No match found anywhere in the text"
                )
                return {
                    "action": "validate",
                    "valid": False,
                    "reason": reason,
                    "error": None,
                }

            if action == "split":
                parts = compiled.split(text, maxsplit=max(0, max_split))
                return {
                    "action": "split",
                    "parts": parts,
                    "count": len(parts),
                    "error": None,
                }

            return {"error": f"Unknown action: {action}"}

        except Exception as exc:
            logger.error("RegexTool error action=%s: %s", action, exc)
            return {"result": None, "error": str(exc)}
