"""
Real web search tool using DuckDuckGo (no API key required).

Uses the duckduckgo-search library which provides free, anonymous
search results without rate limits for reasonable usage.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """
    Searches the web via DuckDuckGo and returns structured results.

    No API key required. Runs the synchronous DDG client in a thread
    pool to avoid blocking the async event loop.
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="web_search",
            description=(
                "Search the internet for current information using DuckDuckGo. "
                "Returns titles, URLs, and snippets. Use for recent events, "
                "facts that may have changed, or topics outside training data."
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
                    "region": {
                        "type": "string",
                        "description": "Region code for results (e.g. 'it-it', 'us-en'). Default 'wt-wt' (global).",
                        "default": "wt-wt",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(
        self,
        query: str,
        num_results: int = 5,
        region: str = "wt-wt",
        **_: Any,
    ) -> list[dict[str, str]]:
        """
        Execute a DuckDuckGo web search.

        Returns a list of {title, url, snippet} dicts.
        Runs in a thread pool to keep the event loop non-blocking.
        """
        num_results = min(max(1, num_results), 10)
        logger.debug("Web search", query=query, n=num_results)

        try:
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._search_sync(query, num_results, region),
            )
            return results
        except Exception as exc:
            logger.error("Web search failed query=%r: %s", query, exc)
            return [{"title": "Search error", "url": "", "snippet": str(exc)}]

    @staticmethod
    def _search_sync(
        query: str, num_results: int, region: str
    ) -> list[dict[str, str]]:
        """Blocking DDG search — called inside run_in_executor."""
        from duckduckgo_search import DDGS

        results: list[dict[str, str]] = []
        with DDGS() as ddgs:
            for r in ddgs.text(
                query,
                region=region,
                safesearch="moderate",
                max_results=num_results,
            ):
                results.append({
                    "title":   r.get("title", ""),
                    "url":     r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        return results
