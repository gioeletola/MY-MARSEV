"""URL Tool — parse, build, encode/decode, and validate URLs."""
from __future__ import annotations

import urllib.parse
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class UrlTool(BaseTool):
    """Parse, build, encode, and validate URLs without external dependencies."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="url_tool",
            description="Parse URLs into components, build URLs from parts, encode/decode query strings, extract domain info.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["parse", "build", "encode", "decode", "extract_domain", "add_params", "clean"],
                        "description": "parse | build | encode | decode | extract_domain | add_params | clean",
                    },
                    "url": {"type": "string", "description": "URL to process"},
                    "base_url": {"type": "string", "description": "Base URL for build action"},
                    "path": {"type": "string", "description": "URL path"},
                    "params": {"type": "object", "description": "Query parameters as key-value pairs"},
                    "text": {"type": "string", "description": "Text to URL-encode or decode"},
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str,
        url: str = "",
        base_url: str = "",
        path: str = "",
        params: dict | None = None,
        text: str = "",
        **_: Any,
    ) -> Any:
        params = params or {}
        try:
            if action == "parse":
                return self._parse(url)
            if action == "build":
                return self._build(base_url, path, params)
            if action == "encode":
                return {"result": urllib.parse.quote(text, safe=""), "error": None}
            if action == "decode":
                return {"result": urllib.parse.unquote(text), "error": None}
            if action == "extract_domain":
                return self._extract_domain(url)
            if action == "add_params":
                return self._add_params(url, params)
            if action == "clean":
                return self._clean(url)
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _parse(self, url: str) -> dict:
        if not url:
            return {"result": None, "error": "url is required"}
        parsed = urllib.parse.urlparse(url)
        query_params = dict(urllib.parse.parse_qsl(parsed.query))
        return {
            "result": {
                "scheme": parsed.scheme,
                "netloc": parsed.netloc,
                "host": parsed.hostname,
                "port": parsed.port,
                "path": parsed.path,
                "query_string": parsed.query,
                "params": query_params,
                "fragment": parsed.fragment,
            },
            "is_absolute": bool(parsed.scheme),
            "error": None,
        }

    def _build(self, base: str, path: str, params: dict) -> dict:
        qs = urllib.parse.urlencode(params) if params else ""
        url = urllib.parse.urljoin(base, path)
        if qs:
            url = f"{url}?{qs}"
        return {"result": url, "error": None}

    def _extract_domain(self, url: str) -> dict:
        parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
        host = parsed.hostname or ""
        parts = host.split(".")
        tld = ".".join(parts[-2:]) if len(parts) >= 2 else host
        subdomain = ".".join(parts[:-2]) if len(parts) > 2 else ""
        return {
            "result": host,
            "tld": tld,
            "subdomain": subdomain,
            "scheme": parsed.scheme,
            "error": None,
        }

    def _add_params(self, url: str, params: dict) -> dict:
        parsed = urllib.parse.urlparse(url)
        existing = dict(urllib.parse.parse_qsl(parsed.query))
        existing.update(params)
        new_qs = urllib.parse.urlencode(existing)
        new_url = urllib.parse.urlunparse(parsed._replace(query=new_qs))
        return {"result": new_url, "added_params": list(params.keys()), "error": None}

    def _clean(self, url: str) -> dict:
        parsed = urllib.parse.urlparse(url)
        clean = urllib.parse.urlunparse((
            parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/",
            "", "", "",
        ))
        return {"result": clean, "removed_fragment": bool(parsed.fragment),
                "removed_query": bool(parsed.query), "error": None}
