"""AdapterRegistry — discover and chain adapters."""
from __future__ import annotations

import logging
import time

from .adapters import (
    CsvToJsonAdapter,
    DictToYamlAdapter,
    JsonToMarkdownAdapter,
    JsonToTableAdapter,
    MarkdownToHtmlAdapter,
)
from .base import BaseAdapter
from .types import AdapterFormat, AdapterResult

logger = logging.getLogger(__name__)

_BUILTINS: list[BaseAdapter] = [
    JsonToMarkdownAdapter(),
    CsvToJsonAdapter(),
    MarkdownToHtmlAdapter(),
    DictToYamlAdapter(),
    JsonToTableAdapter(),
]


class AdapterRegistry:
    """Registry of all adapters. Supports direct conversion and multi-step chains."""

    def __init__(self) -> None:
        self._adapters: dict[str, BaseAdapter] = {}
        for a in _BUILTINS:
            self.register(a)

    def register(self, adapter: BaseAdapter) -> None:
        self._adapters[adapter.adapter_id] = adapter

    def get(self, adapter_id: str) -> BaseAdapter | None:
        return self._adapters.get(adapter_id)

    async def adapt(
        self,
        data: object,
        from_format: AdapterFormat | str,
        to_format: AdapterFormat | str,
    ) -> AdapterResult:
        from_fmt = AdapterFormat(from_format) if isinstance(from_format, str) else from_format
        to_fmt = AdapterFormat(to_format) if isinstance(to_format, str) else to_format
        for adapter in self._adapters.values():
            if adapter.can_adapt(from_fmt, to_fmt):
                return await adapter.adapt(data, from_fmt, to_fmt)
        return AdapterResult(False, None, error=f"No adapter for {from_fmt}→{to_fmt}")

    async def chain(
        self,
        data: object,
        fmt_chain: list[str],
    ) -> AdapterResult:
        """Convert data through a chain of formats: ["json", "markdown", "html"]."""
        if len(fmt_chain) < 2:
            return AdapterResult(False, None, error="Chain needs at least 2 formats")
        result_data = data
        t0 = time.monotonic()
        for i in range(len(fmt_chain) - 1):
            res = await self.adapt(result_data, fmt_chain[i], fmt_chain[i + 1])
            if not res.success:
                return res
            result_data = res.data
        return AdapterResult(True, result_data, duration_ms=(time.monotonic() - t0) * 1000)

    def list_adapters(self) -> list[dict]:
        return [
            {"adapter_id": a.adapter_id, "pairs": [(f.value, t.value) for f, t in a.supported_pairs]}
            for a in self._adapters.values()
        ]
