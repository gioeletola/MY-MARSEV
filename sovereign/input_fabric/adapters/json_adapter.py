"""JSON adapter — serialises a dict/JSON string to readable text."""
from __future__ import annotations
import json
from typing import Any


class JsonAdapter:
    async def extract(self, raw: Any) -> str:
        if isinstance(raw, dict):
            return json.dumps(raw, indent=2, ensure_ascii=False)
        try:
            parsed = json.loads(str(raw))
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except Exception:
            return str(raw)
