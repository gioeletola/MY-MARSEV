"""Text adapter — passes plain text through unchanged."""
from __future__ import annotations
from typing import Any


class TextAdapter:
    async def extract(self, raw: Any) -> str:
        return str(raw)
