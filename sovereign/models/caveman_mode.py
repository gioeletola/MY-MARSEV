"""Caveman mode — hard token budget enforcer that blocks calls exceeding monthly limits."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from sovereign.models.base_provider import BaseProvider, CompletionRequest, CompletionResponse

logger = logging.getLogger(__name__)

_DATA_FILE = Path("data/memory/caveman_budget.json")


@dataclass
class TokenBudget:
    monthly_input_limit: int = 10_000_000
    monthly_output_limit: int = 2_000_000
    daily_input_limit: int = 500_000
    daily_output_limit: int = 100_000
    input_used_month: int = 0
    output_used_month: int = 0
    input_used_day: int = 0
    output_used_day: int = 0
    month_key: str = ""
    day_key: str = ""


class CavemanMode:
    """
    Wraps any provider. Before each call, checks token budget.
    If budget would be exceeded, raises BudgetExceededError.
    Records usage after each successful call.
    """

    class BudgetExceededError(Exception):
        pass

    def __init__(self, provider: BaseProvider, budget: TokenBudget | None = None) -> None:
        self._provider = provider
        self._budget = budget or TokenBudget()
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _month_key(self) -> str:
        return time.strftime("%Y-%m")

    def _day_key(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _load(self) -> None:
        if _DATA_FILE.exists():
            try:
                data = json.loads(_DATA_FILE.read_text())
                self._budget = TokenBudget(**data)
            except Exception:
                pass
        self._reset_if_new_period()

    def _save(self) -> None:
        _DATA_FILE.write_text(json.dumps(self._budget.__dict__, indent=2))

    def _reset_if_new_period(self) -> None:
        mk = self._month_key()
        dk = self._day_key()
        if self._budget.month_key != mk:
            self._budget.input_used_month = 0
            self._budget.output_used_month = 0
            self._budget.month_key = mk
        if self._budget.day_key != dk:
            self._budget.input_used_day = 0
            self._budget.output_used_day = 0
            self._budget.day_key = dk

    def _check_budget(self, estimated_input: int = 500) -> None:
        self._reset_if_new_period()
        if self._budget.input_used_day + estimated_input > self._budget.daily_input_limit:
            raise self.BudgetExceededError(
                f"Daily input token budget exceeded ({self._budget.input_used_day}/{self._budget.daily_input_limit})"
            )
        if self._budget.input_used_month + estimated_input > self._budget.monthly_input_limit:
            raise self.BudgetExceededError(
                f"Monthly input token budget exceeded ({self._budget.input_used_month}/{self._budget.monthly_input_limit})"
            )

    def _record(self, response: CompletionResponse) -> None:
        self._budget.input_used_day += response.input_tokens
        self._budget.input_used_month += response.input_tokens
        self._budget.output_used_day += response.output_tokens
        self._budget.output_used_month += response.output_tokens
        self._save()

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._check_budget()
        response = await self._provider.complete(request)
        self._record(response)
        return response

    def usage_report(self) -> dict:
        self._reset_if_new_period()
        b = self._budget
        return {
            "day": {"input": b.input_used_day, "limit": b.daily_input_limit,
                    "output": b.output_used_day, "output_limit": b.daily_output_limit},
            "month": {"input": b.input_used_month, "limit": b.monthly_input_limit,
                      "output": b.output_used_month, "output_limit": b.monthly_output_limit},
        }

    def set_limits(self, **kwargs: int) -> None:
        for k, v in kwargs.items():
            if hasattr(self._budget, k):
                setattr(self._budget, k, v)
        self._save()
