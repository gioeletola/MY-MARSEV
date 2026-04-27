"""
Spending limits enforcer for SOVEREIGN AI OS.

Tracks per-category spend against configurable daily, monthly, and per-action
ceilings. All spend records are appended to data/ledger/spending.jsonl.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SPENDING_PATH = Path("data/ledger/spending.jsonl")

# ---------------------------------------------------------------------------
# Enums & Dataclasses
# ---------------------------------------------------------------------------


class SpendingCategory(str, Enum):
    TOKENS = "tokens"
    EXTERNAL_API = "external_api"
    OPERATIONS = "operations"
    INVESTMENTS = "investments"
    INFRASTRUCTURE = "infrastructure"


@dataclass
class SpendingLimit:
    """Per-category spending ceiling."""

    category: SpendingCategory
    daily_limit: float
    monthly_limit: float
    per_action_limit: float
    currency: str = "USD"

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "daily_limit": self.daily_limit,
            "monthly_limit": self.monthly_limit,
            "per_action_limit": self.per_action_limit,
            "currency": self.currency,
        }


@dataclass
class SpendRecord:
    """A single recorded spend event."""

    record_id: str
    category: SpendingCategory
    amount: float
    description: str
    currency: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "category": self.category.value,
            "amount": self.amount,
            "description": self.description,
            "currency": self.currency,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpendRecord:
        return cls(
            record_id=data["record_id"],
            category=SpendingCategory(data["category"]),
            amount=data["amount"],
            description=data.get("description", ""),
            currency=data.get("currency", "USD"),
            timestamp=data["timestamp"],
        )


# ---------------------------------------------------------------------------
# Default limits
# ---------------------------------------------------------------------------


def _build_default_limits() -> dict[SpendingCategory, SpendingLimit]:
    return {
        SpendingCategory.TOKENS: SpendingLimit(
            category=SpendingCategory.TOKENS,
            daily_limit=10.0,
            monthly_limit=200.0,
            per_action_limit=1.0,
        ),
        SpendingCategory.EXTERNAL_API: SpendingLimit(
            category=SpendingCategory.EXTERNAL_API,
            daily_limit=50.0,
            monthly_limit=500.0,
            per_action_limit=5.0,
        ),
        SpendingCategory.OPERATIONS: SpendingLimit(
            category=SpendingCategory.OPERATIONS,
            daily_limit=100.0,
            monthly_limit=1000.0,
            per_action_limit=20.0,
        ),
        SpendingCategory.INVESTMENTS: SpendingLimit(
            category=SpendingCategory.INVESTMENTS,
            daily_limit=500.0,
            monthly_limit=5000.0,
            per_action_limit=500.0,
        ),
        SpendingCategory.INFRASTRUCTURE: SpendingLimit(
            category=SpendingCategory.INFRASTRUCTURE,
            daily_limit=200.0,
            monthly_limit=2000.0,
            per_action_limit=50.0,
        ),
    }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SpendingLimitsEngine:
    """
    Enforces configurable spending limits per category.

    Usage::

        engine = SpendingLimitsEngine()
        allowed, reason = engine.check(SpendingCategory.TOKENS, 0.50)
        if allowed:
            engine.record_spend(SpendingCategory.TOKENS, 0.50, "claude-sonnet-4-6 call")
    """

    def __init__(self, persist_path: Path | None = None) -> None:
        self._path: Path = persist_path or _SPENDING_PATH
        self._limits: dict[SpendingCategory, SpendingLimit] = _build_default_limits()
        # Cache of records loaded from disk; new records are appended lazily.
        self._records: list[SpendRecord] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_limit(self, limit: SpendingLimit) -> None:
        """Override the limit for a category."""
        self._limits[limit.category] = limit

    def check(self, category: SpendingCategory, amount: float) -> tuple[bool, str]:
        """
        Verify that *amount* in *category* would not breach any ceiling.

        Returns (True, "") if allowed, or (False, <reason>) if blocked.
        """
        limit = self._limits.get(category)
        if limit is None:
            return True, ""  # No limit configured → allow

        # Per-action check
        if amount > limit.per_action_limit:
            return (
                False,
                f"{category.value}: amount {amount:.4f} exceeds per-action limit "
                f"{limit.per_action_limit:.4f} {limit.currency}",
            )

        # Daily check
        day_used = self.daily_usage(category)
        if day_used + amount > limit.daily_limit:
            return (
                False,
                f"{category.value}: daily usage {day_used:.4f} + {amount:.4f} would exceed "
                f"daily limit {limit.daily_limit:.4f} {limit.currency}",
            )

        # Monthly check
        month_used = self.monthly_usage(category)
        if month_used + amount > limit.monthly_limit:
            return (
                False,
                f"{category.value}: monthly usage {month_used:.4f} + {amount:.4f} would exceed "
                f"monthly limit {limit.monthly_limit:.4f} {limit.currency}",
            )

        return True, ""

    def record_spend(
        self,
        category: SpendingCategory,
        amount: float,
        description: str = "",
    ) -> SpendRecord:
        """Record a spend event and persist it to the ledger."""
        import uuid
        limit = self._limits.get(category)
        currency = limit.currency if limit else "USD"
        record = SpendRecord(
            record_id=str(uuid.uuid4()),
            category=category,
            amount=amount,
            description=description,
            currency=currency,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._records.append(record)
        self._append(record)
        logger.info(
            "SpendingLimitsEngine: recorded %.4f %s in category '%s' — %s",
            amount, currency, category.value, description,
        )
        return record

    def daily_usage(self, category: SpendingCategory) -> float:
        """Sum of all recorded spend for *category* in the current UTC day."""
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(
            r.amount
            for r in self._records
            if r.category == category and r.timestamp.startswith(today)
        )

    def monthly_usage(self, category: SpendingCategory) -> float:
        """Sum of all recorded spend for *category* in the current UTC month (YYYY-MM)."""
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        return sum(
            r.amount
            for r in self._records
            if r.category == category and r.timestamp.startswith(month)
        )

    def summary(self) -> dict[str, Any]:
        """Return a dict with daily/monthly usage and limits for every category."""
        result: dict[str, Any] = {}
        for cat, lim in self._limits.items():
            day = self.daily_usage(cat)
            month = self.monthly_usage(cat)
            result[cat.value] = {
                "daily_used": round(day, 6),
                "daily_limit": lim.daily_limit,
                "daily_remaining": round(max(0.0, lim.daily_limit - day), 6),
                "monthly_used": round(month, 6),
                "monthly_limit": lim.monthly_limit,
                "monthly_remaining": round(max(0.0, lim.monthly_limit - month), 6),
                "per_action_limit": lim.per_action_limit,
                "currency": lim.currency,
            }
        return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _append(self, record: SpendRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict()) + "\n")

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._records.append(SpendRecord.from_dict(json.loads(line)))
                    except Exception as exc:
                        logger.warning("SpendingLimitsEngine: bad ledger line: %s", exc)
        except Exception as exc:
            logger.warning("SpendingLimitsEngine: could not load ledger: %s", exc)
