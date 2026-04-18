"""Signal fusion — combines multiple weak signals into a single weighted forecast."""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    signal_id: str
    source: str
    value: float       # normalised 0–1
    weight: float = 1.0
    confidence: float = 0.7
    label: str = ""


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
    """

    def fuse(self, topic: str, signals: list[Signal], method: str = "weighted_mean") -> FusedForecast:
        if not signals:
            return FusedForecast(topic=topic, signals=[], fused_value=0.5,
                                 fused_confidence=0.0, method=method)

        if method == "weighted_mean":
            total_weight = sum(s.weight * s.confidence for s in signals)
            if total_weight == 0:
                fused = 0.5
            else:
                fused = sum(s.value * s.weight * s.confidence for s in signals) / total_weight
            avg_conf = sum(s.confidence for s in signals) / len(signals)
        elif method == "median":
            sorted_vals = sorted(signals, key=lambda s: s.value)
            mid = len(sorted_vals) // 2
            fused = sorted_vals[mid].value
            avg_conf = sum(s.confidence for s in signals) / len(signals)
        else:
            fused = sum(s.value for s in signals) / len(signals)
            avg_conf = 0.5

        interpretation = self._interpret(fused)
        return FusedForecast(
            topic=topic,
            signals=signals,
            fused_value=round(fused, 3),
            fused_confidence=round(avg_conf, 3),
            method=method,
            interpretation=interpretation,
        )

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

    def consensus(self, signals: list[Signal], threshold: float = 0.7) -> bool:
        """Returns True if signals are in strong agreement above threshold."""
        if not signals:
            return False
        avg = sum(s.value for s in signals) / len(signals)
        return avg >= threshold or avg <= (1.0 - threshold)
