"""
Health monitor — tracks system state and surfaces degradation signals.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HealthStatus:
    """Point-in-time system health snapshot."""

    timestamp: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z"
    )
    overall: str = "ok"          # "ok" | "degraded" | "critical"
    checks: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)


class HealthMonitor:
    """
    Lightweight health monitor for the SOVEREIGN AI OS.

    Tracks:
    - Token budget consumption
    - Error rate
    - Active ephemeral agent count
    - Memory store availability
    - Tool registry status
    """

    def __init__(self) -> None:
        self._errors: list[dict[str, Any]] = []
        self._calls: int = 0
        self._token_budget: int = 200_000
        self._tokens_used: int = 0

    def record_call(self, tokens: int, error: str | None = None) -> None:
        """Record an API call with its token cost and optional error."""
        self._calls += 1
        self._tokens_used += tokens
        if error:
            self._errors.append({"call": self._calls, "error": error})

    def check(
        self,
        tool_registry: Any | None = None,
        agent_registry: Any | None = None,
        factory: Any | None = None,
    ) -> HealthStatus:
        """Run all health checks and return a HealthStatus."""
        checks: dict[str, str] = {}
        alerts: list[str] = []

        # Token budget
        pct = self._tokens_used / self._token_budget if self._token_budget else 0
        checks["token_budget"] = "ok" if pct < 0.8 else "degraded"
        if pct >= 0.95:
            alerts.append(f"Token budget at {pct:.0%} — approaching limit.")

        # Error rate
        recent_errors = self._errors[-10:]
        error_rate = len(recent_errors) / max(self._calls, 1)
        checks["error_rate"] = "ok" if error_rate < 0.3 else "degraded"
        if error_rate >= 0.5:
            alerts.append(f"High error rate: {error_rate:.0%} of last {self._calls} calls.")

        # Tool registry
        if tool_registry is not None:
            checks["tool_registry"] = "ok" if len(tool_registry) > 0 else "degraded"

        # Ephemeral agents
        if factory is not None:
            active = len(factory.list_active())
            checks["ephemeral_agents"] = "ok" if active < 8 else "degraded"
            if active >= 8:
                alerts.append(f"High ephemeral agent count: {active}.")

        overall = "critical" if len(alerts) >= 2 else ("degraded" if alerts else "ok")

        return HealthStatus(
            overall=overall,
            checks=checks,
            metrics={
                "calls": self._calls,
                "tokens_used": self._tokens_used,
                "token_budget_pct": round(pct * 100, 1),
                "error_count": len(self._errors),
            },
            alerts=alerts,
        )
