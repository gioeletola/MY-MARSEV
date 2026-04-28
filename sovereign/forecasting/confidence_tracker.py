"""Confidence tracker — tracks agent prediction accuracy over time."""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path("data/memory/confidence_tracking.json")
_ROLLING_WINDOW = 50    # entries per agent/task for rolling calibration


@dataclass
class PredictionRecord:
    record_id: str
    agent_id: str
    task_type: str
    prediction: str
    predicted_confidence: float
    actual_success: bool | None = None      # True = correct, False = wrong
    correct: bool | None = None             # alias kept for compat
    actual_outcome: str | None = None
    timestamp: float = field(default_factory=time.time)
    resolved_at: float = 0.0


class ConfidenceTracker:
    """
    Records agent predictions with stated confidence levels.

    Provides:
    - Brier score calibration per agent
    - Reliability plot data (bucketed)
    - Rolling window per agent/task_type
    """

    def __init__(self, window: int = _ROLLING_WINDOW) -> None:
        self._records: dict[str, PredictionRecord] = {}
        # rolling window: (agent_id, task_type) → deque of PredictionRecord
        self._rolling: dict[tuple[str, str], deque] = defaultdict(
            lambda: deque(maxlen=window)
        )
        self._window = window
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── Recording & resolution ────────────────────────────────────────────

    def record(
        self,
        agent_id: str,
        prediction: str,
        confidence: float,
        task_type: str = "general",
    ) -> PredictionRecord:
        rec = PredictionRecord(
            record_id=uuid.uuid4().hex[:8],
            agent_id=agent_id,
            task_type=task_type,
            prediction=prediction,
            predicted_confidence=max(0.0, min(1.0, confidence)),
        )
        self._records[rec.record_id] = rec
        self._save()
        return rec

    def update(
        self,
        agent_id: str,
        task_type: str,
        actual_success: bool,
        predicted_confidence: float,
    ) -> PredictionRecord:
        """Calibration feedback — create a resolved record immediately."""
        rec = PredictionRecord(
            record_id=uuid.uuid4().hex[:8],
            agent_id=agent_id,
            task_type=task_type,
            prediction="",
            predicted_confidence=max(0.0, min(1.0, predicted_confidence)),
            actual_success=actual_success,
            correct=actual_success,
            resolved_at=time.time(),
        )
        self._records[rec.record_id] = rec
        key = (agent_id, task_type)
        self._rolling[key].append(rec)
        self._save()
        return rec

    def resolve(
        self, record_id: str, actual_outcome: str, correct: bool
    ) -> bool:
        rec = self._records.get(record_id)
        if not rec:
            return False
        rec.actual_outcome = actual_outcome
        rec.correct = correct
        rec.actual_success = correct
        rec.resolved_at = time.time()
        key = (rec.agent_id, rec.task_type)
        self._rolling[key].append(rec)
        self._save()
        return True

    # ── Calibration metrics ───────────────────────────────────────────────

    def calibration_error(self, agent_id: str) -> float:
        """Brier score for *agent_id* (lower = better calibrated, 0 = perfect)."""
        resolved = self._resolved_for(agent_id)
        if not resolved:
            return float("nan")
        brier = sum(
            (r.predicted_confidence - (1.0 if r.actual_success else 0.0)) ** 2
            for r in resolved
        ) / len(resolved)
        return round(brier, 4)

    def calibration(self, agent_id: str | None = None) -> dict:
        records = [r for r in self._records.values() if r.correct is not None]
        if agent_id:
            records = [r for r in records if r.agent_id == agent_id]
        if not records:
            return {"accuracy": None, "count": 0, "calibration_error": None}

        accuracy = sum(1 for r in records if r.correct) / len(records)
        avg_confidence = sum(r.predicted_confidence for r in records) / len(records)
        calibration_error = abs(accuracy - avg_confidence)
        return {
            "accuracy": round(accuracy, 3),
            "avg_stated_confidence": round(avg_confidence, 3),
            "calibration_error": round(calibration_error, 3),
            "brier_score": self.calibration_error(agent_id or ""),
            "count": len(records),
            "well_calibrated": calibration_error < 0.1,
        }

    def reliability_plot(self, agent_id: str, buckets: int = 10) -> dict:
        """Bucketed calibration data suitable for a reliability diagram.

        Returns:
          {
            "buckets": [{"confidence_low": float, "confidence_high": float,
                         "mean_confidence": float, "accuracy": float, "count": int}, ...],
            "overall_brier": float,
          }
        """
        resolved = self._resolved_for(agent_id)
        if not resolved:
            return {"buckets": [], "overall_brier": float("nan")}

        bucket_size = 1.0 / buckets
        result_buckets = []
        for i in range(buckets):
            lo = i * bucket_size
            hi = lo + bucket_size
            bucket_records = [
                r for r in resolved if lo <= r.predicted_confidence < hi
            ]
            if not bucket_records:
                continue
            mean_conf = sum(r.predicted_confidence for r in bucket_records) / len(bucket_records)
            acc = sum(1 for r in bucket_records if r.actual_success) / len(bucket_records)
            result_buckets.append({
                "confidence_low": round(lo, 2),
                "confidence_high": round(hi, 2),
                "mean_confidence": round(mean_conf, 3),
                "accuracy": round(acc, 3),
                "count": len(bucket_records),
            })

        return {
            "agent_id": agent_id,
            "buckets": result_buckets,
            "overall_brier": self.calibration_error(agent_id),
        }

    def agent_summary(self) -> dict:
        by_agent: dict[str, list[PredictionRecord]] = defaultdict(list)
        for r in self._records.values():
            by_agent[r.agent_id].append(r)
        return {aid: self.calibration(aid) for aid in by_agent}

    # ── Persistence ───────────────────────────────────────────────────────

    def _resolved_for(self, agent_id: str) -> list[PredictionRecord]:
        return [
            r for r in self._records.values()
            if r.agent_id == agent_id
            and r.actual_success is not None
        ]

    def _load(self) -> None:
        if _DATA_FILE.exists():
            try:
                raw = json.loads(_DATA_FILE.read_text())
                self._records = {
                    r["record_id"]: PredictionRecord(**r) for r in raw
                }
            except Exception:
                pass

    def _save(self) -> None:
        try:
            _DATA_FILE.write_text(
                json.dumps(
                    [r.__dict__ for r in self._records.values()], indent=2
                )
            )
        except Exception as exc:
            logger.warning("ConfidenceTracker._save: %s", exc)
