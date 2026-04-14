"""Built-in web search tool stub."""
from __future__ import annotations

from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class WebSearchTool(BaseTool):
    """
    Performs a web search and returns a list of results.

    Stub implementation — wire up to a real search API (Brave, Tavily, SerpAPI, etc.)
    by replacing the execute() body.
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="web_search",
            description=(
                "Search the internet for current information. "
                "Returns a list of relevant results with titles, URLs, and snippets."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string.",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 10).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, query: str, num_results: int = 5, **_: Any) -> list[dict[str, str]]:
        """
        Execute a web search.

        TODO: Replace stub with a real search API call.
        """
        # Stub: return a placeholder result
        return [
            {
                "title": f"[STUB] Search result for: {query}",
                "url": "https://example.com",
                "snippet": (
                    "This is a stub result. Wire up a real search API "
                    "(e.g. Brave Search, Tavily) to get live results."
                ),
            }
        ][:num_results]
