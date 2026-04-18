"""Forecast engine — bridges forecasting module into the proactive event layer."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ForecastAlert:
    alert_id: str
    title: str
    description: str
    probability: float        # 0–1
    impact: str               # low / medium / high / critical
    horizon_days: int
    source: str               # "scenario" | "signal" | "bayesian"
    recommended_action: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0   # 0 = never

    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at


class ForecastEngine:
    """
    Integrates the forecasting subsystem (ScenarioEngine, SignalFusion,
    ConfidenceTracker) with the proactive layer.

    On each evaluation cycle:
    1. Pull active scenarios from ScenarioEngine
    2. Pull fused signals from SignalFusion
    3. Apply probability thresholds → emit ForecastAlerts
    4. Register alerts as Suggestions (via SuggestionEngine) or Events
       (via EventEngine) based on urgency

    Usage::
        fe = ForecastEngine(scenario_engine, signal_fusion, suggestion_engine)
        alerts = await fe.evaluate(memory_snapshot)
    """

    def __init__(
        self,
        scenario_engine: Any | None = None,
        signal_fusion: Any | None = None,
        suggestion_engine: Any | None = None,
        event_engine: Any | None = None,
        high_prob_threshold: float = 0.75,
        medium_prob_threshold: float = 0.45,
    ) -> None:
        self._scenarios = scenario_engine
        self._signals = signal_fusion
        self._suggestions = suggestion_engine
        self._events = event_engine
        self._high_threshold = high_prob_threshold
        self._medium_threshold = medium_prob_threshold
        self._active_alerts: list[ForecastAlert] = []
        self._emitted_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def evaluate(self, memory_snapshot: dict[str, Any]) -> list[ForecastAlert]:
        """Run one evaluation cycle. Returns newly generated alerts."""
        new_alerts: list[ForecastAlert] = []

        # 1. Scenario-based alerts
        if self._scenarios:
            new_alerts.extend(self._alerts_from_scenarios())

        # 2. Signal-based alerts
        if self._signals:
            new_alerts.extend(self._alerts_from_signals(memory_snapshot))

        # 3. Memory-based heuristics (no external deps)
        new_alerts.extend(self._alerts_from_memory(memory_snapshot))

        # Filter expired and de-duplicate
        fresh = [a for a in new_alerts if not a.is_expired and a.alert_id not in self._emitted_ids]
        for a in fresh:
            self._emitted_ids.add(a.alert_id)
        self._active_alerts = [a for a in self._active_alerts if not a.is_expired] + fresh

        # 4. Surface as Suggestions / Events
        self._surface_alerts(fresh)

        logger.info("ForecastEngine: evaluated, %d new alerts", len(fresh))
        return fresh

    async def run_loop(
        self,
        memory_fn: Any,
        interval_s: float = 1800.0,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Recurring evaluation loop (default every 30 min)."""
        logger.info("ForecastEngine: loop started (interval=%.0fs)", interval_s)
        while True:
            if stop_event and stop_event.is_set():
                break
            try:
                snap = await memory_fn() if asyncio.iscoroutinefunction(memory_fn) else memory_fn()
                await self.evaluate(snap)
            except Exception as exc:
                logger.error("ForecastEngine loop error: %s", exc)
            await asyncio.sleep(interval_s)

    def active_alerts(self, min_probability: float = 0.0) -> list[ForecastAlert]:
        return [a for a in self._active_alerts if a.probability >= min_probability
                and not a.is_expired]

    def dismiss(self, alert_id: str) -> bool:
        before = len(self._active_alerts)
        self._active_alerts = [a for a in self._active_alerts if a.alert_id != alert_id]
        return len(self._active_alerts) < before

    # ------------------------------------------------------------------
    # Alert generation
    # ------------------------------------------------------------------

    def _alerts_from_scenarios(self) -> list[ForecastAlert]:
        alerts = []
        try:
            for scenario in self._scenarios.list_all():
                if scenario.probability < self._medium_threshold:
                    continue
                impact = scenario.impact
                alerts.append(ForecastAlert(
                    alert_id=f"scenario_{scenario.scenario_id}",
                    title=f"Scenario alert: {scenario.name}",
                    description=scenario.description,
                    probability=scenario.probability,
                    impact=impact,
                    horizon_days=scenario.time_horizon_days,
                    source="scenario",
                    recommended_action=f"Review scenario '{scenario.name}' and update contingency plan",
                    expires_at=time.time() + scenario.time_horizon_days * 86400,
                ))
        except Exception as exc:
            logger.debug("ForecastEngine._alerts_from_scenarios: %s", exc)
        return alerts

    def _alerts_from_signals(self, snap: dict) -> list[ForecastAlert]:
        alerts = []
        try:
            fused = self._signals.fuse(snap) if hasattr(self._signals, "fuse") else {}
            for key, sig in fused.items():
                prob = float(sig.get("probability", 0))
                if prob < self._medium_threshold:
                    continue
                alerts.append(ForecastAlert(
                    alert_id=f"signal_{key}_{int(time.time()//3600)}",
                    title=sig.get("title", f"Signal: {key}"),
                    description=sig.get("description", ""),
                    probability=prob,
                    impact=sig.get("impact", "medium"),
                    horizon_days=sig.get("horizon_days", 30),
                    source="signal",
                    recommended_action=sig.get("action", "Review signal"),
                    expires_at=time.time() + 86400,
                ))
        except Exception as exc:
            logger.debug("ForecastEngine._alerts_from_signals: %s", exc)
        return alerts

    def _alerts_from_memory(self, snap: dict) -> list[ForecastAlert]:
        """Heuristic alerts derived directly from the memory snapshot."""
        alerts = []
        financial = snap.get("financial", {})

        # Cashflow risk
        cashflow = financial.get("monthly_cashflow") or financial.get("cashflow", None)
        if cashflow is not None:
            cf = float(cashflow)
            if cf < 0:
                alerts.append(ForecastAlert(
                    alert_id="memory_negative_cashflow",
                    title="Negative cashflow detected",
                    description=f"Monthly cashflow is ${cf:,.0f}. Trajectory risk if unchanged.",
                    probability=0.95, impact="high", horizon_days=30,
                    source="bayesian",
                    recommended_action="Run cashflow_analyst for immediate review",
                    expires_at=time.time() + 86400,
                ))
            elif cf < 500:
                alerts.append(ForecastAlert(
                    alert_id="memory_low_cashflow",
                    title="Low cashflow — liquidity risk",
                    description=f"Monthly cashflow is ${cf:,.0f}. Consider reducing expenses.",
                    probability=0.75, impact="medium", horizon_days=60,
                    source="bayesian",
                    recommended_action="Review budget items with budget_manager agent",
                    expires_at=time.time() + 86400 * 3,
                ))

        # Project deadline risk
        projects = snap.get("project", {})
        if isinstance(projects, list):
            overdue = [p for p in projects if p.get("status") == "blocked"]
            if overdue:
                alerts.append(ForecastAlert(
                    alert_id=f"memory_blocked_projects_{len(overdue)}",
                    title=f"{len(overdue)} blocked project(s)",
                    description=f"{', '.join(p.get('name','?') for p in overdue[:3])} are blocked.",
                    probability=0.8, impact="high", horizon_days=14,
                    source="bayesian",
                    recommended_action="Review and unblock projects with coordinator agent",
                    expires_at=time.time() + 86400,
                ))

        return alerts

    # ------------------------------------------------------------------
    # Surface to suggestion/event engine
    # ------------------------------------------------------------------

    def _surface_alerts(self, alerts: list[ForecastAlert]) -> None:
        for alert in alerts:
            # Surface high-probability alerts as Suggestions
            if self._suggestions and alert.probability >= self._high_threshold:
                try:
                    from sovereign.proactive.suggestion_engine import Suggestion
                    sug = Suggestion(
                        suggestion_id=f"forecast_{alert.alert_id}",
                        title=alert.title,
                        description=alert.description,
                        action=alert.recommended_action,
                        priority=alert.probability,
                        source="forecast_engine",
                        expires_at=alert.expires_at,
                    )
                    # Inject directly into suggestion engine's active list
                    if hasattr(self._suggestions, "_active"):
                        self._suggestions._active.append(sug)
                except Exception as exc:
                    logger.debug("ForecastEngine surface suggestion: %s", exc)

            # Surface critical alerts as immediate EventEngine events
            if self._events and alert.impact == "critical":
                try:
                    async def _noop():
                        logger.warning("CRITICAL FORECAST: %s", alert.title)

                    self._events.schedule(
                        event_id=f"forecast_critical_{alert.alert_id}",
                        name=alert.title,
                        callback=_noop,
                        delay_s=5.0,
                    )
                except Exception as exc:
                    logger.debug("ForecastEngine surface event: %s", exc)
