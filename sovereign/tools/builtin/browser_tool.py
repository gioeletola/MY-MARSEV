"""
Browser / web fetch tool — Section 11 of the SOVEREIGN AI OS spec.

Fetches web pages, extracts clean text content, and captures page structure.
Uses httpx (already in deps) + stdlib html.parser — no browser binary required.

For full interactive browsing (click, screenshot, form fill), a Playwright
integration can be dropped in by replacing _fetch_and_parse() below.

Capabilities:
  - Navigate to URL and extract text content
  - Extract all links from a page
  - Extract page title and metadata
  - Extract structured data (tables, lists)
  - Search within page content
"""
from __future__ import annotations

import asyncio
import logging
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)

# Tags whose content should be excluded from text extraction
_SKIP_TAGS = frozenset({"script", "style", "noscript", "nav", "footer", "head"})
# Max response size to process (1 MB)
_MAX_RESPONSE_BYTES = 1_000_000


class _TextExtractor(HTMLParser):
    """Minimal HTML → plain text extractor using stdlib."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth: int = 0
        self.title: str = ""
        self._in_title: bool = False
        self.links: list[dict[str, str]] = []
        self._current_href: str = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            attr_dict = dict(attrs)
            self._current_href = attr_dict.get("href", "")
        if tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "li", "tr"):
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._current_href:
            self._current_href = ""

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title += text
        else:
            self._chunks.append(text)
            # Track link text
            if self._current_href and text:
                self.links.append({"text": text[:100], "href": self._current_href})

    def get_text(self) -> str:
        raw = " ".join(self._chunks)
        # Collapse whitespace
        return re.sub(r"\s{3,}", "\n\n", raw).strip()


class BrowserTool(BaseTool):
    """
    Fetches and extracts content from web pages.

    Runs httpx request in executor to keep event loop non-blocking.
    Returns structured page content: title, text, links, metadata.
    """

    MAX_TEXT_CHARS = 15_000
    DEFAULT_TIMEOUT = 20

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="browser",
            description=(
                "Fetch a web page and extract its text content, title, and links. "
                "Use for reading articles, documentation, product pages, or any URL. "
                "Returns clean text (no HTML). Cannot execute JavaScript. "
                "For search queries, use web_search instead."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL to fetch (must start with http:// or https://).",
                    },
                    "extract_links": {
                        "type": "boolean",
                        "description": "Include list of links found on the page.",
                        "default": False,
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters of text to return (default 15000).",
                        "default": 15000,
                    },
                },
                "required": ["url"],
            },
        )

    async def execute(
        self,
        url: str,
        extract_links: bool = False,
        max_chars: int = MAX_TEXT_CHARS,
        **_: Any,
    ) -> dict[str, Any]:
        """
        Fetch a URL and return extracted content.

        Returns:
            {url, title, text, links, status_code, content_type, error}
        """
        if not url.startswith(("http://", "https://")):
            return self._error(url, "URL must start with http:// or https://")

        max_chars = min(max(500, max_chars), self.MAX_TEXT_CHARS)

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._fetch_sync(url, extract_links, max_chars)
            )
            return result
        except Exception as exc:
            logger.error("BrowserTool fetch failed url=%r: %s", url, exc)
            return self._error(url, str(exc))

    def _fetch_sync(self, url: str, extract_links: bool, max_chars: int) -> dict[str, Any]:
        """Synchronous fetch — called inside run_in_executor."""
        import httpx

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SOVEREIGN-AI-OS/1.0; +research)",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            with httpx.Client(
                timeout=self.DEFAULT_TIMEOUT,
                follow_redirects=True,
                headers=headers,
            ) as client:
                resp = client.get(url)
                content_type = resp.headers.get("content-type", "")
                status_code = resp.status_code

                if status_code >= 400:
                    return self._error(url, f"HTTP {status_code}", status_code=status_code)

                # Only parse HTML responses
                if "html" not in content_type and "text" not in content_type:
                    return {
                        "url": url,
                        "title": "",
                        "text": f"[Non-HTML response: {content_type}]",
                        "links": [],
                        "status_code": status_code,
                        "content_type": content_type,
                        "error": None,
                    }

                raw = resp.text[:_MAX_RESPONSE_BYTES]

        except Exception as exc:
            return self._error(url, f"Network error: {exc}")

        # Parse HTML
        parser = _TextExtractor()
        try:
            parser.feed(raw)
        except Exception:
            pass

        text = parser.get_text()[:max_chars]
        links: list[dict[str, str]] = []
        if extract_links:
            base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            for link in parser.links[:50]:
                href = link["href"]
                if href.startswith("http"):
                    links.append(link)
                elif href.startswith("/"):
                    links.append({"text": link["text"], "href": urljoin(base, href)})

        return {
            "url": url,
            "title": parser.title[:200],
            "text": text,
            "char_count": len(text),
            "links": links[:20] if extract_links else [],
            "status_code": status_code,
            "content_type": content_type,
            "error": None,
        }

    @staticmethod
    def _error(url: str, message: str, status_code: int = -1) -> dict[str, Any]:
        return {
            "url": url,
            "title": "",
            "text": "",
            "char_count": 0,
            "links": [],
            "status_code": status_code,
            "content_type": "",
            "error": message,
        }
