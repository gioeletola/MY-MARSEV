"""
Base tool interface for the SOVEREIGN AI OS tool ecosystem.

All tools implement BaseTool (or satisfy ToolProtocol structurally).
Tool schemas map directly to the Anthropic API ``tools`` parameter format.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class ToolSchema:
    """
    Anthropic API-compatible tool definition.

    Maps 1:1 to one element of the ``tools`` list in the API request.
    """

    name: str
    description: str
    input_schema: dict[str, Any]  # JSON Schema object

    def to_api_dict(self) -> dict[str, Any]:
        """Return the dict format expected by the Anthropic API ``tools`` parameter."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@runtime_checkable
class ToolProtocol(Protocol):
    """Structural protocol — any object with these attributes is a valid tool."""

    @property
    def schema(self) -> ToolSchema: ...

    async def execute(self, **kwargs: Any) -> Any: ...


class BaseTool(ABC):
    """
    Abstract base class for all SOVEREIGN AI OS tools.

    Subclass this, define ``schema`` and ``execute()``, then register
    with ToolRegistry via ``registry.register(MyTool())``.
    """

    # Subclasses may define these class-level attributes as an alternative to
    # overriding the schema property.
    name: str = ""
    description: str = ""
    parameters_schema: dict[str, Any] = {}

    @property
    def schema(self) -> ToolSchema:
        """Return the tool's ToolSchema. Reads class-level attributes by default."""
        return ToolSchema(
            name=self.name,
            description=self.description,
            input_schema=self.parameters_schema,
        )

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """
        Execute the tool with validated kwargs matching the input_schema.

        Must return a JSON-serialisable result.
        On error, raise an exception — the tool registry will catch it.
        """
        ...

    def to_api_dict(self) -> dict[str, Any]:
        """Convenience: return Anthropic API tool dict."""
        return self.schema.to_api_dict()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.schema.name!r})"
