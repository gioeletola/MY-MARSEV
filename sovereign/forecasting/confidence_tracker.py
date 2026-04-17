"""Confidence tracker — tracks agent prediction accuracy over time."""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path("data/memory/confidence_tracking.json")


@dataclass
class PredictionRecord:
    record_id: str
    agent_id: str
    prediction: str
    predicted_confidence: float
    actual_outcome: str | None = None
    correct: bool | None = None
    timestamp: float = field(default_factory=time.time)
    resolved_at: float = 0.0


class ConfidenceTracker:
    """
    Records agent predictions with stated confidence levels.
    When outcomes are known, resolves the prediction and tracks calibration.
    """

    def __init__(self) -> None:
        self._records: dict[str, PredictionRecord] = {}
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if _DATA_FILE.exists():
            try:
                raw = json.loads(_DATA_FILE.read_text())
                self._records = {r["record_id"]: PredictionRecord(**r) for r in raw}
            except Exception:
                pass

    def _save(self) -> None:
        _DATA_FILE.write_text(json.dumps(
            [r.__dict__ for r in self._records.values()], indent=2
        ))

    def record(self, agent_id: str, prediction: str, confidence: float) -> PredictionRecord:
        import uuid
        rec = PredictionRecord(
            record_id=str(uuid.uuid4())[:8],
            agent_id=agent_id,
            prediction=prediction,
            predicted_confidence=confidence,
        )
        self._records[rec.record_id] = rec
        self._save()
        return rec

    def resolve(self, record_id: str, actual_outcome: str, correct: bool) -> bool:
        rec = self._records.get(record_id)
        if not rec:
            return False
        rec.actual_outcome = actual_outcome
        rec.correct = correct
        rec.resolved_at = time.time()
        self._save()
        return True

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
            "count": len(records),
            "well_calibrated": calibration_error < 0.1,
        }

    def agent_summary(self) -> dict:
        by_agent: dict[str, list[PredictionRecord]] = defaultdict(list)
        for r in self._records.values():
            by_agent[r.agent_id].append(r)
        return {
            aid: self.calibration(aid)
            for aid in by_agent
        }
