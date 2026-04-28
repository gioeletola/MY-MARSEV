"""BaseAdapter ABC."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .types import AdapterFormat, AdapterResult


class BaseAdapter(ABC):
    adapter_id: str = "base"
    supported_pairs: list[tuple[AdapterFormat, AdapterFormat]] = []

    def can_adapt(self, from_fmt: AdapterFormat, to_fmt: AdapterFormat) -> bool:
        return (from_fmt, to_fmt) in self.supported_pairs

    @abstractmethod
    async def adapt(self, data: object, from_fmt: AdapterFormat, to_fmt: AdapterFormat) -> AdapterResult:
        ...
