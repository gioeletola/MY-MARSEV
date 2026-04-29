"""Base64 Tool — encode, decode, validate, and inspect base64 strings."""
from __future__ import annotations

import base64
import binascii
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class Base64Tool(BaseTool):
    """Encode/decode data in base64, base64url, and base32 formats."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="base64_tool",
            description="Encode/decode text or bytes in base64, base64url, and base32. Validate base64 strings.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["encode", "decode", "encode_url", "decode_url", "encode_b32", "decode_b32", "is_valid"],
                        "description": "encode|decode|encode_url|decode_url|encode_b32|decode_b32|is_valid",
                    },
                    "text": {"type": "string", "description": "Text or base64 string to process"},
                    "encoding": {"type": "string", "description": "Character encoding (default: utf-8)"},
                },
                "required": ["action", "text"],
            },
        )

    async def execute(self, action: str, text: str = "", encoding: str = "utf-8", **_: Any) -> Any:
        try:
            if action == "encode":
                return {"result": base64.b64encode(text.encode(encoding)).decode(), "error": None}
            if action == "decode":
                decoded = base64.b64decode(text + "==").decode(encoding)
                return {"result": decoded, "error": None}
            if action == "encode_url":
                return {"result": base64.urlsafe_b64encode(text.encode(encoding)).decode().rstrip("="), "error": None}
            if action == "decode_url":
                pad = text + "=" * (4 - len(text) % 4)
                return {"result": base64.urlsafe_b64decode(pad).decode(encoding), "error": None}
            if action == "encode_b32":
                return {"result": base64.b32encode(text.encode(encoding)).decode(), "error": None}
            if action == "decode_b32":
                pad = text + "=" * ((8 - len(text) % 8) % 8)
                return {"result": base64.b32decode(pad.upper()).decode(encoding), "error": None}
            if action == "is_valid":
                try:
                    base64.b64decode(text + "==")
                    return {"result": True, "error": None}
                except (binascii.Error, ValueError):
                    return {"result": False, "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}
