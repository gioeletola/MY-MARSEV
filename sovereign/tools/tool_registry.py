"""
Tool registry for the SOVEREIGN AI OS.

Central store of all available tool instances. Agents request tool
schemas from here; the orchestrator executes tools through here.
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry of all available BaseTool instances.

    Tools are registered once at boot (in SovereignOrchestrator._init_registries).
    Agents receive a reference to the shared registry via dependency injection.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance. Raises ValueError on name collision."""
        name = tool.schema.name
        if name in self._tools:
            raise ValueError(
                f"Tool '{name}' is already registered. "
                "Use a unique name or deregister the existing tool first."
            )
        self._tools[name] = tool
        logger.debug("Registered tool", tool=name)

    def deregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> BaseTool:
        """Return a registered tool by name. Raises KeyError if not found."""
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(
                f"Tool '{name}' not found in registry. "
                f"Available: {list(self._tools)}"
            )

    def list_names(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools)

    def list_schemas(self, allowed: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Return Anthropic API tool dicts for all registered tools.

        Args:
            allowed: If given, only include tools whose name is in this list.
                     Pass an empty list to return no tools.
                     Pass None to return all tools.
        """
        tools = self._tools.values()
        if allowed is not None:
            tools = [t for t in tools if t.schema.name in allowed]  # type: ignore[assignment]
        return [t.to_api_dict() for t in tools]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, name: str, inputs: dict[str, Any]) -> Any:
        """
        Execute a registered tool by name with the given inputs.

        Exceptions from the tool are re-raised with context added.
        """
        tool = self.get(name)
        try:
            result = await tool.execute(**inputs)
            logger.debug("Tool executed", tool=name, success=True)
            return result
        except Exception as exc:
            logger.error("Tool execution failed", tool=name, error=str(exc))
            raise RuntimeError(f"Tool '{name}' failed: {exc}") from exc

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={list(self._tools)})"
