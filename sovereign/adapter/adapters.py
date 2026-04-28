"""Built-in adapter implementations."""
from __future__ import annotations

import csv
import io
import json
import re
import time

from .base import BaseAdapter
from .types import AdapterFormat, AdapterResult

_SUPPORTED = {
    "json_to_markdown": (AdapterFormat.JSON, AdapterFormat.MARKDOWN),
    "csv_to_json":      (AdapterFormat.CSV,  AdapterFormat.JSON),
    "markdown_to_html": (AdapterFormat.MARKDOWN, AdapterFormat.HTML),
    "dict_to_yaml":     (AdapterFormat.JSON, AdapterFormat.YAML),
    "json_to_text":     (AdapterFormat.JSON, AdapterFormat.TEXT),
    "json_to_table":    (AdapterFormat.JSON, AdapterFormat.TABLE),
}


class JsonToMarkdownAdapter(BaseAdapter):
    adapter_id = "json_to_markdown"
    supported_pairs = [(AdapterFormat.JSON, AdapterFormat.MARKDOWN)]

    async def adapt(self, data: object, from_fmt: AdapterFormat, to_fmt: AdapterFormat) -> AdapterResult:
        t0 = time.monotonic()
        try:
            if isinstance(data, str):
                data = json.loads(data)
            lines = ["```json\n" + json.dumps(data, indent=2) + "\n```"]
            if isinstance(data, dict):
                lines = [f"**{k}**: {v}" for k, v in data.items()]
            elif isinstance(data, list):
                lines = [f"- {json.dumps(item)}" for item in data]
            result = "\n".join(lines)
            return AdapterResult(True, result, self.adapter_id, "json", "markdown",
                                 (time.monotonic() - t0) * 1000)
        except Exception as exc:
            return AdapterResult(False, None, self.adapter_id, error=str(exc))


class CsvToJsonAdapter(BaseAdapter):
    adapter_id = "csv_to_json"
    supported_pairs = [(AdapterFormat.CSV, AdapterFormat.JSON)]

    async def adapt(self, data: object, from_fmt: AdapterFormat, to_fmt: AdapterFormat) -> AdapterResult:
        t0 = time.monotonic()
        try:
            text = data if isinstance(data, str) else data.decode()  # type: ignore[union-attr]
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            return AdapterResult(True, rows, self.adapter_id, "csv", "json",
                                 (time.monotonic() - t0) * 1000)
        except Exception as exc:
            return AdapterResult(False, None, self.adapter_id, error=str(exc))


class MarkdownToHtmlAdapter(BaseAdapter):
    adapter_id = "markdown_to_html"
    supported_pairs = [(AdapterFormat.MARKDOWN, AdapterFormat.HTML)]

    _RULES = [
        (re.compile(r"^### (.+)$", re.M),  r"<h3>\1</h3>"),
        (re.compile(r"^## (.+)$", re.M),   r"<h2>\1</h2>"),
        (re.compile(r"^# (.+)$", re.M),    r"<h1>\1</h1>"),
        (re.compile(r"\*\*(.+?)\*\*"),     r"<strong>\1</strong>"),
        (re.compile(r"\*(.+?)\*"),         r"<em>\1</em>"),
        (re.compile(r"`(.+?)`"),           r"<code>\1</code>"),
        (re.compile(r"^- (.+)$", re.M),    r"<li>\1</li>"),
        (re.compile(r"\[(.+?)\]\((.+?)\)"), r'<a href="\2">\1</a>'),
    ]

    async def adapt(self, data: object, from_fmt: AdapterFormat, to_fmt: AdapterFormat) -> AdapterResult:
        t0 = time.monotonic()
        try:
            text = str(data)
            for pattern, repl in self._RULES:
                text = pattern.sub(repl, text)
            html = f"<div class='markdown-body'>{text}</div>"
            return AdapterResult(True, html, self.adapter_id, "markdown", "html",
                                 (time.monotonic() - t0) * 1000)
        except Exception as exc:
            return AdapterResult(False, None, self.adapter_id, error=str(exc))


class DictToYamlAdapter(BaseAdapter):
    adapter_id = "dict_to_yaml"
    supported_pairs = [(AdapterFormat.JSON, AdapterFormat.YAML)]

    def _to_yaml(self, obj: object, indent: int = 0) -> str:
        pad = "  " * indent
        if isinstance(obj, dict):
            lines = []
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{pad}{k}:")
                    lines.append(self._to_yaml(v, indent + 1))
                else:
                    lines.append(f"{pad}{k}: {json.dumps(v)}")
            return "\n".join(lines)
        if isinstance(obj, list):
            return "\n".join(f"{pad}- {json.dumps(i)}" for i in obj)
        return f"{pad}{json.dumps(obj)}"

    async def adapt(self, data: object, from_fmt: AdapterFormat, to_fmt: AdapterFormat) -> AdapterResult:
        t0 = time.monotonic()
        try:
            if isinstance(data, str):
                data = json.loads(data)
            yaml_str = self._to_yaml(data)
            return AdapterResult(True, yaml_str, self.adapter_id, "json", "yaml",
                                 (time.monotonic() - t0) * 1000)
        except Exception as exc:
            return AdapterResult(False, None, self.adapter_id, error=str(exc))


class JsonToTableAdapter(BaseAdapter):
    adapter_id = "json_to_table"
    supported_pairs = [(AdapterFormat.JSON, AdapterFormat.TABLE)]

    async def adapt(self, data: object, from_fmt: AdapterFormat, to_fmt: AdapterFormat) -> AdapterResult:
        t0 = time.monotonic()
        try:
            if isinstance(data, str):
                data = json.loads(data)
            if not isinstance(data, list) or not data:
                return AdapterResult(False, None, self.adapter_id, error="Expected list of dicts")
            headers = list(data[0].keys()) if isinstance(data[0], dict) else []
            sep = " | "
            header_row = sep.join(headers)
            divider = " | ".join("---" for _ in headers)
            rows = [sep.join(str(row.get(h, "")) for h in headers) for row in data if isinstance(row, dict)]
            table = "\n".join([header_row, divider] + rows)
            return AdapterResult(True, table, self.adapter_id, "json", "table",
                                 (time.monotonic() - t0) * 1000)
        except Exception as exc:
            return AdapterResult(False, None, self.adapter_id, error=str(exc))
