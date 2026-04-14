"""
Tool router — resolves which tools are appropriate for a given task context.
"""
from __future__ import annotations

from sovereign.tools.tool_registry import ToolRegistry


class ToolRouter:
    """
    Suggests which tools should be made available to an agent for a given task.

    In the current stub implementation, routing is based on simple keyword
    matching on the task objective. Replace with an LLM-based classifier
    or rule engine for production use.
    """

    # Maps keyword fragments to tool names
    _KEYWORD_MAP: dict[str, list[str]] = {
        "search": ["web_search"],
        "web": ["web_search"],
        "internet": ["web_search"],
        "file": ["file_ops"],
        "read file": ["file_ops"],
        "write file": ["file_ops"],
        "code": ["code_exec"],
        "execute": ["code_exec"],
        "run": ["code_exec"],
        "memory": ["memory_tool"],
        "remember": ["memory_tool"],
        "recall": ["memory_tool"],
    }

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def suggest_tools(self, objective: str) -> list[str]:
        """
        Return a list of tool names that are likely useful for the objective.

        Only returns names of tools that are actually registered.
        """
        objective_lower = objective.lower()
        suggested: set[str] = set()
        for keyword, tools in self._KEYWORD_MAP.items():
            if keyword in objective_lower:
                for tool in tools:
                    if tool in self._registry.list_names():
                        suggested.add(tool)
        return sorted(suggested)
