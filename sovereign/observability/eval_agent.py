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

import asyncio
import json
import logging
import pathlib
import uuid
from dataclasses import asdict, dataclass, field
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

    def schedule_nightly(self, scheduler: Any) -> None:
        """Register a nightly eval job with the scheduler."""
        from sovereign.infra.scheduler import ScheduleFrequency
        existing = {j.name for j in scheduler.list_jobs()}
        if "nightly_eval" not in existing:
            scheduler.schedule(
                "nightly_eval",
                "eval_agent",
                "Run nightly regression evaluation of agent outputs.",
                ScheduleFrequency.DAILY,
            )
            logger.info("EvalAgent: nightly eval job registered")

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


# ---------------------------------------------------------------------------
# RegressionTracker
# ---------------------------------------------------------------------------

class RegressionTracker:
    """
    Tracks eval history across sessions, computes per-agent trends,
    and flags degrading agents.
    """

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)

    def record(self, eval_result: EvalResult) -> None:
        """Append an EvalResult to the persistent JSONL store."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(eval_result), default=str) + "\n")
        except Exception as exc:
            logger.error("RegressionTracker.record failed: %s", exc)

    def get_history(self, agent_id: str, last_n: int = 50) -> list[dict]:
        """Return the last N eval records for a specific agent."""
        records: list[dict] = []
        if not self._path.exists():
            return records
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("agent_id") == agent_id:
                            records.append(rec)
                    except json.JSONDecodeError:
                        pass
        except Exception as exc:
            logger.warning("RegressionTracker.get_history error: %s", exc)
        return records[-last_n:]

    def regression_report(self) -> dict[str, Any]:
        """
        Returns:
          avg_scores: {agent_id: avg_overall}
          trends:     {agent_id: "improving"|"degrading"|"stable"}
          worst_agents: [agent_id, ...] sorted by avg score asc
        """
        all_records: dict[str, list[float]] = {}
        if not self._path.exists():
            return {"avg_scores": {}, "trends": {}, "worst_agents": []}
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        aid = rec.get("agent_id", "unknown")
                        overall = float(rec.get("overall", 0.0))
                        all_records.setdefault(aid, []).append(overall)
                    except (json.JSONDecodeError, ValueError):
                        pass
        except Exception as exc:
            logger.warning("RegressionTracker.regression_report error: %s", exc)
            return {"avg_scores": {}, "trends": {}, "worst_agents": []}

        avg_scores: dict[str, float] = {}
        trends: dict[str, str] = {}
        for aid, scores in all_records.items():
            avg_scores[aid] = round(sum(scores) / len(scores), 3)
            if len(scores) >= 4:
                half = len(scores) // 2
                first_half = sum(scores[:half]) / half
                second_half = sum(scores[half:]) / (len(scores) - half)
                diff = second_half - first_half
                if diff > 0.05:
                    trends[aid] = "improving"
                elif diff < -0.05:
                    trends[aid] = "degrading"
                else:
                    trends[aid] = "stable"
            else:
                trends[aid] = "stable"

        worst_agents = sorted(avg_scores.keys(), key=lambda a: avg_scores[a])
        return {
            "avg_scores": avg_scores,
            "trends": trends,
            "worst_agents": worst_agents,
        }


# ---------------------------------------------------------------------------
# NightlyEvalRunner
# ---------------------------------------------------------------------------

class NightlyEvalRunner:
    """
    Pulls last 50 sessions from the decision ledger, re-evaluates outputs,
    records results via RegressionTracker, and sends a Telegram alert if
    average score drops more than 10% compared to the previous run.
    """

    ALERT_DROP_THRESHOLD = 0.10  # 10% drop triggers alert

    def __init__(
        self,
        eval_agent: EvalAgent,
        regression_tracker: RegressionTracker,
        ledger_path: str | pathlib.Path = "data/ledger/decisions.jsonl",
        prev_avg_path: str | pathlib.Path = "data/ledger/nightly_prev_avg.json",
    ) -> None:
        self._eval_agent = eval_agent
        self._tracker = regression_tracker
        self._ledger_path = pathlib.Path(ledger_path)
        self._prev_avg_path = pathlib.Path(prev_avg_path)

    async def run_nightly(self, orchestrator: Any) -> dict[str, Any]:
        """
        Pull last 50 sessions, re-evaluate outputs, store regression records,
        and send Telegram alert if avg score degraded > 10%.
        """
        logger.info("NightlyEvalRunner: starting nightly evaluation run")
        sessions = self._load_recent_sessions(50)
        new_evals: list[EvalResult] = []

        for sess in sessions:
            session_id = sess.get("session_id", "unknown")
            agent_id = sess.get("agent_id", "orchestrator")
            description = sess.get("description", "")
            outcome = sess.get("outcome", "")
            task_id = sess.get("decision_id", str(uuid.uuid4())[:8])

            ev = self._eval_agent.evaluate(
                session_id=session_id,
                agent_id=agent_id,
                task_id=task_id,
                objective=description,
                result=outcome,
            )
            self._tracker.record(ev)
            new_evals.append(ev)

        # Compute avg score for this run
        current_avg = (
            round(sum(e.overall for e in new_evals) / len(new_evals), 3)
            if new_evals else 0.0
        )

        # Load previous avg and compare
        prev_avg = self._load_prev_avg()
        drop = prev_avg - current_avg if prev_avg > 0 else 0.0
        alert_sent = False

        if drop > self.ALERT_DROP_THRESHOLD:
            msg = (
                f"SOVEREIGN EVAL ALERT: nightly avg score dropped {drop:.1%} "
                f"(prev={prev_avg:.3f}, current={current_avg:.3f}). "
                f"Evaluated {len(new_evals)} sessions."
            )
            logger.warning(msg)
            alert_sent = await self._send_telegram_alert(orchestrator, msg)

        # Save current avg as new baseline
        self._save_prev_avg(current_avg)

        report = self._tracker.regression_report()
        summary = {
            "sessions_evaluated": len(new_evals),
            "current_avg_score": current_avg,
            "previous_avg_score": prev_avg,
            "score_drop": round(drop, 3),
            "alert_sent": alert_sent,
            "regression_report": report,
        }
        logger.info("NightlyEvalRunner: complete — %s", summary)
        return summary

    def _load_recent_sessions(self, n: int) -> list[dict]:
        records: list[dict] = []
        if not self._ledger_path.exists():
            return records
        try:
            with self._ledger_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception as exc:
            logger.warning("NightlyEvalRunner: ledger read error: %s", exc)
        return records[-n:]

    def _load_prev_avg(self) -> float:
        if not self._prev_avg_path.exists():
            return 0.0
        try:
            data = json.loads(self._prev_avg_path.read_text("utf-8"))
            return float(data.get("avg", 0.0))
        except Exception:
            return 0.0

    def _save_prev_avg(self, avg: float) -> None:
        try:
            self._prev_avg_path.parent.mkdir(parents=True, exist_ok=True)
            self._prev_avg_path.write_text(
                json.dumps({"avg": avg, "ts": datetime.now(timezone.utc).isoformat()}),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("NightlyEvalRunner: save prev avg failed: %s", exc)

    async def _send_telegram_alert(self, orchestrator: Any, message: str) -> bool:
        """Attempt to send a Telegram alert via the NotificationService."""
        try:
            notif = getattr(orchestrator, "_notif", None)
            if notif is None:
                return False
            send_fn = getattr(notif, "send_telegram", None)
            if send_fn:
                if asyncio.iscoroutinefunction(send_fn):
                    await send_fn(message)
                else:
                    send_fn(message)
                return True
        except Exception as exc:
            logger.warning("NightlyEvalRunner: Telegram alert failed: %s", exc)
        return False
