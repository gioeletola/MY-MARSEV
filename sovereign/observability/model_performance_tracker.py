"""
Model Performance Tracker — per-model latency, cost, error-rate, and confidence metrics.

Persists to data/memory/model_perf.json on every record call.
Uses GaussianBelief for running Bayesian latency estimation.
"""
from __future__ import annotations

import json
import logging
import pathlib
import statistics
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/memory/model_perf.json")


@dataclass
class _ModelRecord:
    """Runtime record for a single model."""
    model_id: str
    latencies: list[float] = field(default_factory=list)
    tokens_in_total: int = 0
    tokens_out_total: int = 0
    cost_usd_total: float = 0.0
    call_count: int = 0
    error_count: int = 0
    confidence_sum: float = 0.0

    def add(
        self,
        latency_ms: float,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        confidence: float,
        success: bool,
    ) -> None:
        self.latencies.append(latency_ms)
        self.tokens_in_total += tokens_in
        self.tokens_out_total += tokens_out
        self.cost_usd_total += cost_usd
        self.call_count += 1
        self.confidence_sum += confidence
        if not success:
            self.error_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "latencies": self.latencies,
            "tokens_in_total": self.tokens_in_total,
            "tokens_out_total": self.tokens_out_total,
            "cost_usd_total": round(self.cost_usd_total, 6),
            "call_count": self.call_count,
            "error_count": self.error_count,
            "confidence_sum": round(self.confidence_sum, 6),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "_ModelRecord":
        rec = cls(model_id=d["model_id"])
        rec.latencies = d.get("latencies", [])
        rec.tokens_in_total = d.get("tokens_in_total", 0)
        rec.tokens_out_total = d.get("tokens_out_total", 0)
        rec.cost_usd_total = d.get("cost_usd_total", 0.0)
        rec.call_count = d.get("call_count", 0)
        rec.error_count = d.get("error_count", 0)
        rec.confidence_sum = d.get("confidence_sum", 0.0)
        return rec


def _percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile (0-100) of *data*."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (p / 100) * (len(sorted_data) - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= len(sorted_data):
        return sorted_data[-1]
    frac = idx - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


class ModelPerformanceTracker:
    """
    Tracks per-model performance metrics: latency, tokens, cost, error rate,
    and confidence. Persists state to JSON on every record call.

    Uses GaussianBelief from sovereign.forecasting.probabilistic_models for
    running latency tracking (mean/std) per model.
    """

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._records: dict[str, _ModelRecord] = {}
        self._beliefs: dict[str, Any] = {}  # model_id → GaussianBelief
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        model_id: str,
        latency_ms: float,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        confidence: float,
        success: bool,
    ) -> None:
        """Record a single model call."""
        if model_id not in self._records:
            self._records[model_id] = _ModelRecord(model_id=model_id)
        self._records[model_id].add(
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            confidence=confidence,
            success=success,
        )

        # Update GaussianBelief for latency
        belief = self._get_belief(model_id)
        belief.update(latency_ms)

        self._persist()

    def get_stats(self, model_id: str) -> dict[str, Any]:
        """
        Return stats for a single model:
          mean/p50/p95/p99 latency, total calls, error_rate,
          avg_confidence, total_cost_usd, gaussian belief summary.
        """
        rec = self._records.get(model_id)
        if rec is None or rec.call_count == 0:
            return {"model_id": model_id, "total_calls": 0}

        lats = rec.latencies
        belief = self._get_belief(model_id)
        return {
            "model_id": model_id,
            "total_calls": rec.call_count,
            "error_rate": round(rec.error_count / rec.call_count, 4),
            "avg_confidence": round(rec.confidence_sum / rec.call_count, 4),
            "total_cost_usd": round(rec.cost_usd_total, 6),
            "tokens_in_total": rec.tokens_in_total,
            "tokens_out_total": rec.tokens_out_total,
            "latency_ms": {
                "mean": round(statistics.mean(lats), 2) if lats else 0.0,
                "p50": round(_percentile(lats, 50), 2),
                "p95": round(_percentile(lats, 95), 2),
                "p99": round(_percentile(lats, 99), 2),
            },
            "gaussian_belief": belief.to_dict(),
        }

    def compare_models(self) -> list[dict[str, Any]]:
        """
        Return models sorted by composite score (lower is better):
            composite = mean_latency_ms * cost_per_call * (1 + error_rate)

        Models with no calls are excluded.
        """
        results = []
        for model_id, rec in self._records.items():
            if rec.call_count == 0:
                continue
            mean_lat = statistics.mean(rec.latencies) if rec.latencies else 0.0
            cost_per_call = rec.cost_usd_total / rec.call_count
            error_rate = rec.error_count / rec.call_count
            composite = mean_lat * max(cost_per_call, 1e-9) * (1.0 + error_rate)
            results.append({
                "model_id": model_id,
                "composite_score": round(composite, 8),
                "mean_latency_ms": round(mean_lat, 2),
                "cost_per_call_usd": round(cost_per_call, 6),
                "error_rate": round(error_rate, 4),
                "total_calls": rec.call_count,
            })
        return sorted(results, key=lambda x: x["composite_score"])

    def to_dict(self) -> dict[str, Any]:
        """Return full stats dict for all tracked models."""
        return {mid: self.get_stats(mid) for mid in self._records}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_belief(self, model_id: str) -> Any:
        if model_id not in self._beliefs:
            try:
                from sovereign.forecasting.probabilistic_models import GaussianBelief
                belief = GaussianBelief(label=f"latency_{model_id}")
                # Replay existing latency data so belief is consistent with record
                rec = self._records.get(model_id)
                if rec:
                    for lat in rec.latencies:
                        belief.update(lat)
                self._beliefs[model_id] = belief
            except Exception as exc:
                logger.warning("ModelPerformanceTracker: GaussianBelief import failed: %s", exc)
                self._beliefs[model_id] = _FallbackBelief(model_id)
        return self._beliefs[model_id]

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {mid: rec.to_dict() for mid, rec in self._records.items()}
            self._path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        except Exception as exc:
            logger.error("ModelPerformanceTracker._persist failed: %s", exc)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text("utf-8"))
            for mid, data in raw.items():
                self._records[mid] = _ModelRecord.from_dict(data)
            logger.info(
                "ModelPerformanceTracker: loaded %d model records", len(self._records)
            )
        except Exception as exc:
            logger.warning("ModelPerformanceTracker._load failed: %s", exc)


class _FallbackBelief:
    """Minimal fallback when GaussianBelief is unavailable."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._vals: list[float] = []

    def update(self, x: float) -> None:
        self._vals.append(x)

    def to_dict(self) -> dict[str, Any]:
        mean = statistics.mean(self._vals) if self._vals else 0.0
        return {"label": self.label, "n": len(self._vals), "mean": round(mean, 4)}
