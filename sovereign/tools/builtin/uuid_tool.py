"""UUID Tool — generate and inspect UUIDs."""
from __future__ import annotations

import uuid
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class UuidTool(BaseTool):
    """Generate v1/v4/v5 UUIDs, validate, inspect, and convert formats."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="uuid_tool",
            description="Generate UUID v1/v4/v5, validate UUID strings, convert to different formats (hex, int, urn).",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["generate", "validate", "inspect", "to_hex", "to_int", "to_urn", "bulk"],
                        "description": "generate|validate|inspect|to_hex|to_int|to_urn|bulk",
                    },
                    "value": {"type": "string", "description": "UUID string to process"},
                    "version": {"type": "integer", "description": "UUID version: 1, 4 (default), or 5"},
                    "namespace": {"type": "string", "description": "Namespace UUID for v5 (default: DNS)"},
                    "name": {"type": "string", "description": "Name string for v5"},
                    "count": {"type": "integer", "description": "How many to generate for bulk (max 50)"},
                },
                "required": ["action"],
            },
        )

    async def execute(
        self, action: str, value: str = "", version: int = 4,
        namespace: str = "", name: str = "", count: int = 5, **_: Any,
    ) -> Any:
        try:
            if action == "generate":
                return {"result": self._gen(version, namespace, name), "version": version, "error": None}
            if action == "bulk":
                n = max(1, min(count, 50))
                return {"result": [self._gen(version, namespace, name) for _ in range(n)], "count": n, "error": None}
            if action == "validate":
                try:
                    uid = uuid.UUID(value)
                    return {"result": True, "version": uid.version, "variant": str(uid.variant), "error": None}
                except ValueError:
                    return {"result": False, "error": None}
            if action == "inspect":
                uid = uuid.UUID(value)
                return {
                    "result": str(uid),
                    "version": uid.version,
                    "variant": str(uid.variant),
                    "hex": uid.hex,
                    "int": uid.int,
                    "urn": uid.urn,
                    "time": uid.time if uid.version == 1 else None,
                    "error": None,
                }
            if action == "to_hex":
                return {"result": uuid.UUID(value).hex, "error": None}
            if action == "to_int":
                return {"result": uuid.UUID(value).int, "error": None}
            if action == "to_urn":
                return {"result": uuid.UUID(value).urn, "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _gen(self, version: int, namespace: str, name: str) -> str:
        if version == 1:
            return str(uuid.uuid1())
        if version == 5:
            ns = uuid.UUID(namespace) if namespace else uuid.NAMESPACE_DNS
            return str(uuid.uuid5(ns, name or "sovereign"))
        return str(uuid.uuid4())
