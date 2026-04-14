"""Built-in memory read/write tool for agents."""
from __future__ import annotations

from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class MemoryTool(BaseTool):
    """
    Allows agents to read from and write to the memory system directly.

    The memory_manager is injected at construction time. This makes memory
    operations explicit tool calls visible in the action log.
    """

    def __init__(self, memory_manager: Any) -> None:
        self._memory = memory_manager

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="memory_tool",
            description=(
                "Read from or write to the SOVEREIGN AI OS memory system. "
                "Use action='read' to look up a key, 'write' to store data, "
                "'search' for semantic search across memory."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "search"],
                        "description": "Memory operation to perform.",
                    },
                    "domain": {
                        "type": "string",
                        "description": (
                            "Memory domain name: identity, operational, project, "
                            "relationship, financial, learning, inventory, "
                            "health_routine, diary, legal_compliance, decision, "
                            "research, content, brand."
                        ),
                    },
                    "key": {
                        "type": "string",
                        "description": "Record key for read/write operations.",
                    },
                    "value": {
                        "type": "object",
                        "description": "Data to store (required for action='write').",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query (required for action='search').",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str,
        domain: str = "",
        key: str = "",
        value: dict[str, Any] | None = None,
        query: str = "",
        **_: Any,
    ) -> Any:
        """Execute a memory operation."""
        if action == "read":
            if not domain or not key:
                return {"error": "domain and key are required for read"}
            return await self._memory.read(domain, key)

        if action == "write":
            if not domain or not key or value is None:
                return {"error": "domain, key, and value are required for write"}
            await self._memory.write(domain, key, value)
            return {"written": True, "domain": domain, "key": key}

        if action == "search":
            if not query:
                return {"error": "query is required for search"}
            results = await self._memory.semantic_search(
                query=query,
                domain=domain or None,
                top_k=5,
            )
            return {"results": results}

        return {"error": f"Unknown action: {action}"}
