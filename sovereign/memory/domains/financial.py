"""
Memory domain: financial — net worth, cashflow, transactions, portfolio.
Stores data in data/memory/financial.json.
"""
from __future__ import annotations

import csv
import io
import json
from sovereign.memory._atomic_io import _save_json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_FILE = Path("data/memory/financial.json")
DOMAIN_NAME = "financial"


class FinancialMemoryStore:
    """
    Persistent store for all financial data.

    JSON structure:
      { "snapshot": {...}, "holdings": [...], "transactions": [...] }
    """

    def __init__(self, data_file: Path = _DATA_FILE) -> None:
        self._path = data_file
        self._data: dict[str, Any] = self._load()

    # ── persistence ─────────────────────────────────────────────────────

    def _load(self) -> dict[str, Any]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            return {"snapshot": {}, "holdings": [], "transactions": []}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {"snapshot": {}, "holdings": [], "transactions": []}

    def _save(self) -> None:
        _save_json(self._path, self._data, ensure_ascii=False)

    # ── snapshot (KPIs) ─────────────────────────────────────────────────

    def get_snapshot(self) -> dict[str, Any]:
        snap = dict(self._data.get("snapshot", {}))
        income   = float(snap.get("monthly_income",   0.0))
        expenses = float(snap.get("monthly_expenses", 0.0))
        snap.setdefault("monthly_cashflow", round(income - expenses, 2))
        if income > 0:
            snap["savings_rate"] = round((income - expenses) / income * 100, 1)
        holdings = self._data.get("holdings", [])
        if holdings:
            snap["net_worth"] = round(sum(float(h.get("value", 0)) for h in holdings), 2)
        return snap

    def set_snapshot(self, **kwargs: Any) -> None:
        self._data.setdefault("snapshot", {}).update(kwargs)
        self._data["snapshot"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    # ── portfolio ────────────────────────────────────────────────────────

    def get_portfolio(self) -> list[dict[str, Any]]:
        return list(self._data.get("holdings", []))

    def set_holding(self, name: str, asset_class: str, value: float, **kwargs: Any) -> None:
        holdings = self._data.setdefault("holdings", [])
        for h in holdings:
            if h.get("name") == name:
                h.update({"value": value, "asset_class": asset_class, **kwargs})
                self._save()
                return
        holdings.append({
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "asset_class": asset_class,
            "value": value,
            "cost_basis": kwargs.get("cost_basis", 0.0),
            "quantity":   kwargs.get("quantity",   0.0),
            "ticker":     kwargs.get("ticker",     ""),
            "currency":   kwargs.get("currency",   "USD"),
        })
        self._save()

    def get_portfolio_by_class(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for h in self._data.get("holdings", []):
            cls = h.get("asset_class", "other")
            result[cls] = result.get(cls, 0.0) + float(h.get("value", 0))
        return result

    # ── transactions ─────────────────────────────────────────────────────

    def add_transaction(
        self,
        date_str: str,
        description: str,
        amount: float,
        category: str = "uncategorized",
        source: str = "manual",
        account: str = "",
    ) -> dict[str, Any]:
        tx = {
            "tx_id":       str(uuid.uuid4())[:8],
            "date":        date_str,
            "description": description,
            "amount":      round(amount, 2),
            "category":    category,
            "source":      source,
            "account":     account,
            "created_at":  datetime.now(timezone.utc).isoformat(),
        }
        self._data.setdefault("transactions", []).append(tx)
        self._save()
        return tx

    def get_transactions(
        self,
        limit: int = 50,
        date_from: str = "",
        date_to:   str = "",
        category:  str = "",
    ) -> list[dict[str, Any]]:
        txs = list(self._data.get("transactions", []))
        if date_from:
            txs = [t for t in txs if t.get("date", "") >= date_from]
        if date_to:
            txs = [t for t in txs if t.get("date", "") <= date_to]
        if category:
            txs = [t for t in txs if t.get("category") == category]
        return list(reversed(txs))[:limit]

    def get_cashflow_by_month(self, months: int = 12) -> list[dict[str, Any]]:
        monthly: dict[str, dict[str, float]] = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
        for tx in self._data.get("transactions", []):
            d   = tx.get("date", "")[:7]  # YYYY-MM
            amt = float(tx.get("amount", 0))
            if amt >= 0:
                monthly[d]["income"]   += amt
            else:
                monthly[d]["expenses"] += abs(amt)
        sorted_months = sorted(monthly.keys())[-months:]
        result = []
        for m in sorted_months:
            income   = round(monthly[m]["income"],   2)
            expenses = round(monthly[m]["expenses"], 2)
            result.append({
                "month":     m,
                "income":    income,
                "expenses":  expenses,
                "cashflow":  round(income - expenses, 2),
            })
        return result

    def import_csv_transactions(
        self,
        csv_text: str,
        date_col:   str = "date",
        desc_col:   str = "description",
        amount_col: str = "amount",
        source:     str = "csv_import",
    ) -> dict[str, Any]:
        """Parse a CSV string and bulk-import transactions. Returns {imported, skipped, errors}."""
        imported = 0
        skipped  = 0
        errors:  list[str] = []
        try:
            reader  = csv.DictReader(io.StringIO(csv_text))
            headers = reader.fieldnames or []

            def _find(preferred: str) -> str | None:
                exact = next((h for h in headers if h.lower() == preferred.lower()), None)
                if exact:
                    return exact
                return next((h for h in headers if preferred.lower() in h.lower()), None)

            date_key   = _find(date_col)
            desc_key   = _find(desc_col)
            amount_key = _find(amount_col)
            # Fallback patterns
            if not date_key:
                date_key = next((h for h in headers if any(p in h.lower() for p in ("date","datum","data"))), None)
            if not desc_key:
                desc_key = next((h for h in headers if any(p in h.lower() for p in ("desc","merchant","payee","memo","label","narr"))), None)
            if not amount_key:
                amount_key = next((h for h in headers if any(p in h.lower() for p in ("amount","debit","credit","sum","value"))), None)

            for row in reader:
                try:
                    date_str    = (row.get(date_key or "")   or "").strip()
                    description = (row.get(desc_key or "")   or "").strip()
                    amount_str  = (row.get(amount_key or "") or "0").strip().replace(",","").replace("$","").replace("€","")
                    if not date_str or not amount_str:
                        skipped += 1
                        continue
                    # Normalize date
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                        try:
                            date_str = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            pass
                    self.add_transaction(date_str, description, float(amount_str), source=source)
                    imported += 1
                except Exception as exc:
                    errors.append(str(exc))
                    skipped += 1
        except Exception as exc:
            errors.append(f"CSV parse error: {exc}")

        logger.info("CSV import: %d imported, %d skipped", imported, skipped)
        return {"imported": imported, "skipped": skipped, "errors": errors}

    def get_summary(self) -> dict[str, Any]:
        snap    = self.get_snapshot()
        holdings = self.get_portfolio()
        return {
            "net_worth":         snap.get("net_worth",        0.0),
            "monthly_income":    snap.get("monthly_income",   0.0),
            "monthly_expenses":  snap.get("monthly_expenses", 0.0),
            "monthly_cashflow":  snap.get("monthly_cashflow", 0.0),
            "savings_rate":      snap.get("savings_rate",     0.0),
            "portfolio_total":   sum(float(h.get("value", 0)) for h in holdings),
            "portfolio_by_class": self.get_portfolio_by_class(),
            "transaction_count": len(self._data.get("transactions", [])),
            "recent_transactions": self.get_transactions(limit=10),
            "cashflow_12m":      self.get_cashflow_by_month(months=12),
            "updated_at":        snap.get("updated_at", ""),
        }
