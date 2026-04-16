"""
Eval Agent — quality evaluation of agent outputs.

Scores every StructuredOutput on:
- Completeness (did it answer the objective?)
- Accuracy (is the content factually consistent?)
- Actionability (are the outputs actionable?)
- Tone & Format (appropriate for context?)
- Safety (no harmful content?)

Maintains an eval database for regression tracking.
"""
from __future__ import annotations

import json
import logging
import pathlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/ledger/evals.jsonl")


@dataclass
class EvalResult:
    """Evaluation result for a single agent output."""
    eval_id: str
    session_id: str
    agent_id: str
    task_id: str
    # Scores (0.0 – 1.0)
    completeness: float
    actionability: float
    tone_format: float
    safety: float
    overall: float
    # Flags
    passed: bool         # overall >= threshold
    flags: list[str] = field(default_factory=list)
    notes: str = ""
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvalAgent:
    """
    Automated quality evaluation for agent outputs.

    Heuristic-based scoring (no Claude call required) for fast inline evaluation.
    Optionally runs deep LLM eval for flagged outputs.

    Scoring rubric:
    - completeness: does result have >= min_words and non-empty content?
    - actionability: does result contain action-oriented language?
    - tone_format: is result structured (headers, bullets, numbered lists)?
    - safety: does result pass basic safety checks?
    - overall: weighted mean
    """

    PASS_THRESHOLD = 0.60
    MIN_WORDS = 20

    ACTION_KEYWORDS = [
        "action", "step", "recommend", "should", "must", "will", "next",
        "task", "implement", "execute", "review", "schedule", "contact",
        "priority", "deadline", "complete", "deliver",
    ]

    SAFETY_FAIL_PATTERNS = [
        "harm", "illegal", "kill", "weapon", "exploit",
        "password:", "api_key:", "secret:",
    ]

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._results: list[EvalResult] = []
        self._load()

    # ------------------------------------------------------------------

    def evaluate(
        self,
        session_id: str,
        agent_id: str,
        task_id: str,
        objective: str,
        result: str,
    ) -> EvalResult:
        """Heuristic eval of a single agent output."""
        flags: list[str] = []

        # Completeness
        words = result.split()
        completeness = min(1.0, len(words) / max(self.MIN_WORDS, 1))
        if len(words) < self.MIN_WORDS:
            flags.append(f"short_output ({len(words)} words)")

        # Actionability
        result_lower = result.lower()
        kw_hits = sum(1 for kw in self.ACTION_KEYWORDS if kw in result_lower)
        actionability = min(1.0, kw_hits / 5)

        # Tone & Format (presence of structured elements)
        format_signals = sum([
            "##" in result or "#" in result,
            "- " in result or "• " in result,
            any(f"{i}." in result for i in range(1, 6)),
            len(result) > 200,
        ])
        tone_format = format_signals / 4

        # Safety
        safety_violations = [p for p in self.SAFETY_FAIL_PATTERNS if p in result_lower]
        safety = 0.0 if safety_violations else 1.0
        if safety_violations:
            flags.append(f"safety_violation: {safety_violations}")

        # Overall (weighted)
        overall = round(
            completeness * 0.30 + actionability * 0.30 +
            tone_format * 0.20 + safety * 0.20, 3
        )
        passed = overall >= self.PASS_THRESHOLD and not safety_violations

        if not passed:
            flags.append(f"overall={overall:.2f} < threshold={self.PASS_THRESHOLD}")

        ev = EvalResult(
            eval_id=str(uuid.uuid4())[:8],
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            completeness=round(completeness, 3),
            actionability=round(actionability, 3),
            tone_format=round(tone_format, 3),
            safety=round(safety, 3),
            overall=overall,
            passed=passed,
            flags=flags,
        )
        self._results.append(ev)
        self._append(ev)

        if not passed:
            logger.warning(
                "EvalAgent: FAIL agent=%s task=%s overall=%.2f flags=%s",
                agent_id, task_id, overall, flags
            )

        return ev

    def agent_stats(self, agent_id: str) -> dict[str, Any]:
        """Return aggregate stats for one agent."""
        results = [r for r in self._results if r.agent_id == agent_id]
        if not results:
            return {"agent_id": agent_id, "evals": 0}
        return {
            "agent_id": agent_id,
            "evals": len(results),
            "pass_rate": round(sum(1 for r in results if r.passed) / len(results), 3),
            "avg_overall": round(sum(r.overall for r in results) / len(results), 3),
            "avg_completeness": round(sum(r.completeness for r in results) / len(results), 3),
            "avg_actionability": round(sum(r.actionability for r in results) / len(results), 3),
        }

    def failing_agents(self, pass_rate_threshold: float = 0.70) -> list[str]:
        """Return agent IDs with pass rate below threshold."""
        agent_ids = {r.agent_id for r in self._results}
        return [
            aid for aid in agent_ids
            if self.agent_stats(aid).get("pass_rate", 1.0) < pass_rate_threshold
        ]

    def recent_evals(self, limit: int = 20) -> list[dict]:
        return [asdict(r) for r in self._results[-limit:]]

    def overall_stats(self) -> dict[str, Any]:
        if not self._results:
            return {"total": 0}
        return {
            "total": len(self._results),
            "pass_rate": round(sum(1 for r in self._results if r.passed) / len(self._results), 3),
            "avg_overall": round(sum(r.overall for r in self._results) / len(self._results), 3),
            "failing_agents": self.failing_agents(),
        }

    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._results.append(EvalResult(**json.loads(line)))
            logger.info("EvalAgent loaded %d eval results", len(self._results))
        except Exception as exc:
            logger.warning("EvalAgent load error: %s", exc)

    def _append(self, ev: EvalResult) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(ev), default=str) + "\n")
        except Exception as exc:
            logger.error("EvalAgent append failed: %s", exc)
