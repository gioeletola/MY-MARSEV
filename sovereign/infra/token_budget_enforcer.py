"""Hard token spending gates — enforced before every Claude API call."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path("data/memory/token_budget.json")


@dataclass
class BudgetEntry:
    agent_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)


class TokenBudgetExceeded(Exception):
    pass


class TokenBudgetEnforcer:
    """
    Tracks per-agent and global token spend. Raises TokenBudgetExceeded
    before a call would exceed the configured daily / monthly caps.
    """

    def __init__(
        self,
        daily_token_limit: int = 2_000_000,
        monthly_token_limit: int = 50_000_000,
        daily_cost_limit_usd: float = 20.0,
        monthly_cost_limit_usd: float = 300.0,
    ) -> None:
        self.daily_token_limit = daily_token_limit
        self.monthly_token_limit = monthly_token_limit
        self.daily_cost_limit_usd = daily_cost_limit_usd
        self.monthly_cost_limit_usd = monthly_cost_limit_usd
        self._entries: list[BudgetEntry] = []
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── persistence ────────────────────────────────────────────────────────

    def _load(self) -> None:
        if _DATA_FILE.exists():
            try:
                raw = json.loads(_DATA_FILE.read_text())
                self._entries = [BudgetEntry(**e) for e in raw]
            except Exception:
                self._entries = []

    def _save(self) -> None:
        _DATA_FILE.write_text(
            json.dumps([e.__dict__ for e in self._entries[-5000:]], indent=2)
        )

    # ── period helpers ─────────────────────────────────────────────────────

    def _day_start(self) -> float:
        import datetime
        today = datetime.date.today()
        return time.mktime(today.timetuple())

    def _month_start(self) -> float:
        import datetime
        d = datetime.date.today().replace(day=1)
        return time.mktime(d.timetuple())

    def _entries_since(self, since: float) -> list[BudgetEntry]:
        return [e for e in self._entries if e.timestamp >= since]

    # ── enforcement ────────────────────────────────────────────────────────

    def check(self, estimated_tokens: int = 1000, estimated_cost_usd: float = 0.01) -> None:
        """Raise TokenBudgetExceeded if limits would be breached."""
        day_entries = self._entries_since(self._day_start())
        month_entries = self._entries_since(self._month_start())

        day_tokens = sum(e.input_tokens + e.output_tokens for e in day_entries)
        day_cost = sum(e.cost_usd for e in day_entries)
        month_tokens = sum(e.input_tokens + e.output_tokens for e in month_entries)
        month_cost = sum(e.cost_usd for e in month_entries)

        if day_tokens + estimated_tokens > self.daily_token_limit:
            raise TokenBudgetExceeded(
                f"Daily token limit: {day_tokens:,}/{self.daily_token_limit:,}"
            )
        if day_cost + estimated_cost_usd > self.daily_cost_limit_usd:
            raise TokenBudgetExceeded(
                f"Daily cost limit: ${day_cost:.2f}/${self.daily_cost_limit_usd:.2f}"
            )
        if month_tokens + estimated_tokens > self.monthly_token_limit:
            raise TokenBudgetExceeded(
                f"Monthly token limit: {month_tokens:,}/{self.monthly_token_limit:,}"
            )
        if month_cost + estimated_cost_usd > self.monthly_cost_limit_usd:
            raise TokenBudgetExceeded(
                f"Monthly cost limit: ${month_cost:.2f}/${self.monthly_cost_limit_usd:.2f}"
            )

    def record(self, agent_id: str, input_tokens: int, output_tokens: int, cost_usd: float = 0.0) -> None:
        entry = BudgetEntry(agent_id=agent_id, input_tokens=input_tokens,
                            output_tokens=output_tokens, cost_usd=cost_usd)
        self._entries.append(entry)
        self._save()

    # ── reporting ──────────────────────────────────────────────────────────

    def daily_summary(self) -> dict:
        entries = self._entries_since(self._day_start())
        tokens = sum(e.input_tokens + e.output_tokens for e in entries)
        cost = sum(e.cost_usd for e in entries)
        return {"tokens": tokens, "limit": self.daily_token_limit,
                "cost_usd": round(cost, 4), "limit_usd": self.daily_cost_limit_usd,
                "calls": len(entries)}

    def monthly_summary(self) -> dict:
        entries = self._entries_since(self._month_start())
        tokens = sum(e.input_tokens + e.output_tokens for e in entries)
        cost = sum(e.cost_usd for e in entries)
        return {"tokens": tokens, "limit": self.monthly_token_limit,
                "cost_usd": round(cost, 4), "limit_usd": self.monthly_cost_limit_usd,
                "calls": len(entries)}

    def top_consumers(self, n: int = 10) -> list[dict]:
        from collections import defaultdict
        by_agent: dict[str, dict] = defaultdict(lambda: {"tokens": 0, "cost_usd": 0.0, "calls": 0})
        for e in self._entries:
            by_agent[e.agent_id]["tokens"] += e.input_tokens + e.output_tokens
            by_agent[e.agent_id]["cost_usd"] += e.cost_usd
            by_agent[e.agent_id]["calls"] += 1
        ranked = sorted(by_agent.items(), key=lambda x: x[1]["tokens"], reverse=True)
        return [{"agent_id": k, **v} for k, v in ranked[:n]]
