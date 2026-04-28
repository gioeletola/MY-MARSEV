"""Signal fusion — combines multiple weak signals into a single weighted forecast."""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Anomaly threshold: signals more than this many std-devs from mean are flagged
_ANOMALY_SIGMA = 2.0


@dataclass
class Signal:
    # Positional: signal_id, source, value, ...
    signal_id: str = ""
    source: str = "unknown"
    value: float = 0.5       # normalised 0–1
    confidence: float = 0.7
    weight: float = 1.0
    timestamp: float = field(default_factory=time.time)
    label: str = ""


@dataclass
class FusedSignal:
    fused_value: float = 0.5
    fused_confidence: float = 0.0
    conflicts: list[str] = field(default_factory=list)   # sources that conflicted with consensus
    sources: list[str] = field(default_factory=list)     # all contributing source names
    method: str = "weighted_mean"
    interpretation: str = ""
    anomalies: list[str] = field(default_factory=list)
    fused_at: float = field(default_factory=time.time)

    # Aliases for legacy code that used value/confidence
    @property
    def value(self) -> float:
        return self.fused_value

    @property
    def confidence(self) -> float:
        return self.fused_confidence


# Keep old name for backwards compat
@dataclass
class FusedForecast:
    topic: str
    signals: list[Signal]
    fused_value: float
    fused_confidence: float
    method: str = "weighted_mean"
    interpretation: str = ""


class SignalFusion:
    """
    Combines signals from multiple sources (agents, tools, external feeds)
    into a single directional forecast using weighted averaging.

    New capability: ``fuse()`` uses the new ``Signal``/``FusedSignal`` types,
    while the legacy ``fuse(topic, signals, method)`` signature still works.
    """

    def __init__(self) -> None:
        # Rolling history per source for anomaly detection
        self._history: dict[str, list[float]] = {}

    # ── New unified API ───────────────────────────────────────────────────

    def fuse(self, topic_or_signals: "str | list[Signal]", signals: "list[Signal] | None" = None) -> FusedSignal:  # type: ignore[override]
        """Fuse a list of Signal objects into a FusedSignal.

        Accepts both:
          fuse(signals)             — new API
          fuse("topic", signals)   — topic is informational only
        """
        if isinstance(topic_or_signals, str):
            # Called as fuse("topic", signals)
            actual_signals: list[Signal] = signals or []
        else:
            actual_signals = topic_or_signals
        signals = actual_signals

        if not signals:
            return FusedSignal(
                fused_value=0.5, fused_confidence=0.0,
                conflicts=[], sources=[],
                interpretation="No signals",
            )

        # --- Weighted average ---
        total_weight = sum(s.weight * s.confidence for s in signals)
        if total_weight == 0:
            fused_value = sum(s.value for s in signals) / len(signals)
        else:
            fused_value = sum(s.value * s.weight * s.confidence for s in signals) / total_weight

        avg_conf = sum(s.confidence for s in signals) / len(signals)
        fused_value = round(fused_value, 4)

        # --- Conflict detection ---
        conflicts: list[str] = []
        for s in signals:
            if abs(s.value - fused_value) > 0.3:
                conflicts.append(s.source)

        # --- Anomaly detection ---
        anomalies: list[str] = []
        for s in signals:
            hist = self._history.setdefault(s.source, [])
            if len(hist) >= 5:
                mean = sum(hist) / len(hist)
                variance = sum((x - mean) ** 2 for x in hist) / len(hist)
                std = math.sqrt(variance) if variance > 0 else 0.0
                if std > 0 and abs(s.value - mean) > _ANOMALY_SIGMA * std:
                    anomalies.append(s.source)
                    logger.warning(
                        "SignalFusion: anomaly detected from '%s' (value=%.3f, mean=%.3f, std=%.3f)",
                        s.source, s.value, mean, std,
                    )
            hist.append(s.value)
            # Keep rolling window of 50
            if len(hist) > 50:
                self._history[s.source] = hist[-50:]

        return FusedSignal(
            fused_value=fused_value,
            fused_confidence=round(avg_conf, 4),
            conflicts=conflicts,
            sources=[s.source for s in signals],
            method="weighted_mean",
            interpretation=self._interpret(fused_value),
            anomalies=anomalies,
        )

    # ── Legacy API (topic-based) ──────────────────────────────────────────

    def fuse_topic(
        self, topic: str, signals: list[Signal], method: str = "weighted_mean"
    ) -> FusedForecast:
        """Legacy interface: fuse signals for a named topic."""
        if not signals:
            return FusedForecast(topic=topic, signals=[], fused_value=0.5,
                                 fused_confidence=0.0, method=method)

        if method == "weighted_mean":
            total_weight = sum(s.weight * s.confidence for s in signals)
            fused = (
                sum(s.value * s.weight * s.confidence for s in signals) / total_weight
                if total_weight > 0 else 0.5
            )
            avg_conf = sum(s.confidence for s in signals) / len(signals)
        elif method == "median":
            sorted_vals = sorted(signals, key=lambda s: s.value)
            mid = len(sorted_vals) // 2
            fused = sorted_vals[mid].value
            avg_conf = sum(s.confidence for s in signals) / len(signals)
        else:
            fused = sum(s.value for s in signals) / len(signals)
            avg_conf = 0.5

        return FusedForecast(
            topic=topic,
            signals=signals,
            fused_value=round(fused, 3),
            fused_confidence=round(avg_conf, 3),
            method=method,
            interpretation=self._interpret(fused),
        )

    def consensus(self, signals: list[Signal], threshold: float = 0.7) -> bool:
        """Returns True if signals are in strong agreement above threshold."""
        if not signals:
            return False
        avg = sum(s.value for s in signals) / len(signals)
        return avg >= threshold or avg <= (1.0 - threshold)

    def _interpret(self, value: float) -> str:
        if value >= 0.8:
            return "Strong positive signal"
        elif value >= 0.6:
            return "Moderate positive signal"
        elif value >= 0.4:
            return "Neutral / uncertain"
        elif value >= 0.2:
            return "Moderate negative signal"
        else:
            return "Strong negative signal"
