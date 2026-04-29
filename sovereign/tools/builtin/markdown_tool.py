"""Markdown Tool — parse, generate, convert, and validate Markdown."""
from __future__ import annotations

import re
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class MarkdownTool(BaseTool):
    """Generate and manipulate Markdown: headings, tables, code blocks, TOC, stats."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="markdown_tool",
            description="Generate Markdown tables, code blocks, headings, TOC, badges. Extract headings, links. Convert simple markdown to plain text.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["table", "code_block", "heading", "toc", "extract_links",
                                 "extract_headings", "to_plain", "badge", "stats", "list_to_md"],
                        "description": "table|code_block|heading|toc|extract_links|extract_headings|to_plain|badge|stats|list_to_md",
                    },
                    "text": {"type": "string", "description": "Markdown or plain text to process"},
                    "headers": {"type": "array", "description": "Column headers for table"},
                    "rows": {"type": "array", "description": "Table rows (list of lists)"},
                    "language": {"type": "string", "description": "Language for code_block"},
                    "code": {"type": "string", "description": "Code content for code_block"},
                    "level": {"type": "integer", "description": "Heading level 1–6"},
                    "title": {"type": "string", "description": "Heading text"},
                    "items": {"type": "array", "description": "List items"},
                    "ordered": {"type": "boolean", "description": "Ordered list (true) vs unordered (false)"},
                    "label": {"type": "string", "description": "Badge label"},
                    "message": {"type": "string", "description": "Badge message"},
                    "color": {"type": "string", "description": "Badge color"},
                },
                "required": ["action"],
            },
        )

    async def execute(
        self, action: str, text: str = "", headers: list | None = None,
        rows: list | None = None, language: str = "", code: str = "",
        level: int = 2, title: str = "", items: list | None = None,
        ordered: bool = False, label: str = "", message: str = "", color: str = "blue",
        **_: Any,
    ) -> Any:
        try:
            if action == "table":
                return self._table(headers or [], rows or [])
            if action == "code_block":
                return {"result": f"```{language}\n{code}\n```", "error": None}
            if action == "heading":
                lvl = max(1, min(6, level))
                return {"result": f"{'#' * lvl} {title}", "error": None}
            if action == "toc":
                return self._toc(text)
            if action == "extract_links":
                return self._extract_links(text)
            if action == "extract_headings":
                return self._extract_headings(text)
            if action == "to_plain":
                return self._to_plain(text)
            if action == "badge":
                url = f"https://img.shields.io/badge/{label.replace('-','--')}-{message.replace('-','--')}-{color}"
                return {"result": f"![{label}]({url})", "url": url, "error": None}
            if action == "stats":
                return self._stats(text)
            if action == "list_to_md":
                if ordered:
                    md = "\n".join(f"{i+1}. {item}" for i, item in enumerate(items or []))
                else:
                    md = "\n".join(f"- {item}" for item in (items or []))
                return {"result": md, "count": len(items or []), "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _table(self, headers: list, rows: list) -> dict:
        if not headers:
            return {"result": "", "error": "headers required"}
        sep = "| " + " | ".join("---" for _ in headers) + " |"
        header_row = "| " + " | ".join(str(h) for h in headers) + " |"
        data_rows = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
        md = "\n".join([header_row, sep] + data_rows)
        return {"result": md, "rows": len(rows), "cols": len(headers), "error": None}

    def _toc(self, text: str) -> dict:
        headings = re.findall(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE)
        toc_lines = []
        for hashes, title in headings:
            indent = "  " * (len(hashes) - 1)
            anchor = re.sub(r"[^\w\s-]", "", title.lower()).strip().replace(" ", "-")
            toc_lines.append(f"{indent}- [{title}](#{anchor})")
        return {"result": "\n".join(toc_lines), "heading_count": len(headings), "error": None}

    def _extract_links(self, text: str) -> dict:
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
        return {
            "result": [{"text": t, "url": u} for t, u in links],
            "count": len(links),
            "error": None,
        }

    def _extract_headings(self, text: str) -> dict:
        headings = re.findall(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE)
        return {
            "result": [{"level": len(h), "text": t} for h, t in headings],
            "count": len(headings),
            "error": None,
        }

    def _to_plain(self, text: str) -> dict:
        plain = re.sub(r"#{1,6}\s+", "", text)
        plain = re.sub(r"\*\*(.+?)\*\*", r"\1", plain)
        plain = re.sub(r"\*(.+?)\*", r"\1", plain)
        plain = re.sub(r"__(.+?)__", r"\1", plain)
        plain = re.sub(r"`(.+?)`", r"\1", plain)
        plain = re.sub(r"```[\w]*\n.*?```", "", plain, flags=re.DOTALL)
        plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
        plain = re.sub(r"^[-*+]\s+", "", plain, flags=re.MULTILINE)
        plain = re.sub(r"^\d+\.\s+", "", plain, flags=re.MULTILINE)
        plain = re.sub(r"\n{3,}", "\n\n", plain)
        return {"result": plain.strip(), "original_length": len(text), "plain_length": len(plain.strip()), "error": None}

    def _stats(self, text: str) -> dict:
        headings = re.findall(r"^#{1,6}\s+.+$", text, re.MULTILINE)
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
        code_blocks = re.findall(r"```[\w]*\n.*?```", text, re.DOTALL)
        inline_code = re.findall(r"`[^`]+`", text)
        words = len(text.split())
        return {
            "result": {
                "words": words,
                "characters": len(text),
                "headings": len(headings),
                "links": len(links),
                "code_blocks": len(code_blocks),
                "inline_code": len(inline_code),
                "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
            },
            "error": None,
        }
