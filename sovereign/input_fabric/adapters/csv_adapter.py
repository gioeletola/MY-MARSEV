"""CSV adapter — converts CSV text to a readable tabular representation."""
from __future__ import annotations

import csv
import io
from typing import Any


class CsvAdapter:
    async def extract(self, raw: Any) -> str:
        text = str(raw)
        try:
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                return text
            headers = list(rows[0].keys())
            lines = [" | ".join(headers)]
            lines.append("-" * len(lines[0]))
            for row in rows[:50]:  # Cap at 50 rows for prompt injection safety
                lines.append(" | ".join(str(row.get(h, "")) for h in headers))
            if len(rows) > 50:
                lines.append(f"... ({len(rows) - 50} more rows)")
            return "\n".join(lines)
        except Exception:
            return text
