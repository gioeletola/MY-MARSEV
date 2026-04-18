"""
CSV Import Tool — import bank statement CSV files into the financial memory store.

Parameters:
  action:     "import" | "preview"
  csv_text:   raw CSV string content
  filepath:   absolute path to a CSV file (alternative to csv_text)
  date_col:   column name hint for date   (default "date")
  desc_col:   column name hint for description (default "description")
  amount_col: column name hint for amount (default "amount")

Returns:
  {"imported": N, "skipped": M, "errors": [...]}  — for "import"
  {"headers": [...], "preview_rows": [...]}        — for "preview"
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)


class CSVImportTool(BaseTool):

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="csv_import",
            description="Import bank statement or financial CSV files into the financial memory store.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["import", "preview"],
                        "description": "import: save to memory store. preview: parse and return first 10 rows.",
                    },
                    "csv_text": {
                        "type": "string",
                        "description": "Raw CSV string content to import.",
                    },
                    "filepath": {
                        "type": "string",
                        "description": "Absolute path to a CSV file (used if csv_text is not provided).",
                    },
                    "date_col":   {"type": "string", "default": "date"},
                    "desc_col":   {"type": "string", "default": "description"},
                    "amount_col": {"type": "string", "default": "amount"},
                },
                "required": ["action"],
            },
        )

    async def execute(
        self,
        action: str = "import",
        csv_text: str = "",
        filepath: str = "",
        date_col: str = "date",
        desc_col: str = "description",
        amount_col: str = "amount",
        **_: Any,
    ) -> dict[str, Any]:
        # Load from file if csv_text not provided
        if not csv_text and filepath:
            try:
                csv_text = Path(filepath).read_text(encoding="utf-8")
            except Exception as exc:
                return {"result": None, "error": f"Cannot read file: {exc}"}

        if not csv_text:
            return {"result": None, "error": "No CSV content provided (use csv_text or filepath)."}

        try:
            from sovereign.memory.domains.financial import FinancialMemoryStore
            store = FinancialMemoryStore()

            if action == "preview":
                import csv
                import io
                reader = csv.DictReader(io.StringIO(csv_text))
                rows = [row for _, row in zip(range(10), reader)]
                return {
                    "result": {
                        "headers": reader.fieldnames or [],
                        "preview_rows": rows,
                        "total_preview": len(rows),
                    },
                    "error": None,
                }

            result = store.import_csv_transactions(
                csv_text,
                date_col=date_col,
                desc_col=desc_col,
                amount_col=amount_col,
            )
            return {"result": result, "error": None}
        except Exception as exc:
            logger.error("csv_import failed: %s", exc)
            return {"result": None, "error": str(exc)}
