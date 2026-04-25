"""
Agent Level System — SOVEREIGN AI OS.

Agents are classified into 3 operational levels:
  LEVEL_1 — Persona Agent: consultation only, no autonomous actions
  LEVEL_2 — Workflow Agent: structured process, memory, output
  LEVEL_3 — Autonomous Operational Agent: triggers, tools, state, escalation
"""
from __future__ import annotations

import datetime
import json
import logging
import time
from abc import ABC
from dataclasses import dataclass, field
from enum import IntEnum
from enum import Enum
from pathlib import Path
from typing import Any

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Level taxonomy
# ---------------------------------------------------------------------------


class AgentLevel(IntEnum):
    """
    Operational tier classification for agents.

    LEVEL_1 — Persona Agent: consultation only, no autonomous actions.
    LEVEL_2 — Workflow Agent: structured 7-step process, memory, output.
    LEVEL_3 — Autonomous Operational Agent: triggers, tools, persistent state,
               escalation, and ApprovalGate integration.
    """

    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3


class WorkflowStep(str, Enum):
    """
    Ordered steps of the standard 7-step operational workflow.

    LEVEL_2 agents run all steps; LEVEL_3 agents additionally drive
    external triggers and escalation paths.
    """

    OBSERVE = "observe"
    ANALYZE = "analyze"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    REPORT = "report"
    SAVE_MEMORY = "save_memory"


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass
class WorkflowResult:
    """
    Captures the outcome of a single workflow step.

    step:        Which step produced this result.
    status:      One of "ok", "skipped", or "failed".
    data:        Step-specific output dict.
    duration_ms: Wall-clock time for this step (milliseconds).
    timestamp:   ISO-8601 UTC timestamp when the step completed.
    """

    step: WorkflowStep
    status: str  # "ok" | "skipped" | "failed"
    data: dict[str, Any]
    duration_ms: float
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z"
    )


@dataclass
class AgentState:
    """
    Persistent, per-agent operational state.

    Serialised to / deserialised from a JSON file so state survives
    across process restarts.  The history list is capped at 50 entries.
    """

    agent_id: str
    open_tasks: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)  # last 50 actions


@dataclass
class AgentSpec:
    """
    Static metadata describing an agent's operational contract.

    agent_id:               Unique agent identifier (matches BaseAgent.agent_id).
    level:                  AgentLevel classification.
    mission:                One-sentence mission statement.
    triggers:               Event names that activate this agent.
    tools_allowed:          Tool IDs the agent may invoke.
    escalate_to:            agent_id to escalate blocked / high-risk tasks to.
    requires_approval_for:  Action-type strings that must pass ApprovalGate.
    success_metric:         Human-readable success criterion.
    failure_condition:      Human-readable condition that constitutes failure.
    confidence_threshold:   Minimum confidence score to accept a result (0–1).
    """

    agent_id: str
    level: AgentLevel
    mission: str
    triggers: list[str]
    tools_allowed: list[str]
    escalate_to: str
    requires_approval_for: list[str]
    success_metric: str
    failure_condition: str
    confidence_threshold: float = 0.7


# ---------------------------------------------------------------------------
# Abstract leveled agent base
# ---------------------------------------------------------------------------

_STATE_DIR = Path(".sovereign_state")


class LeveledAgent(BaseAgent, ABC):
    """
    Abstract base for LEVEL_2 and LEVEL_3 agents.

    Implements a concrete ``run()`` method that drives the standard 7-step
    workflow (OBSERVE → ANALYZE → PLAN → EXECUTE → VERIFY → REPORT →
    SAVE_MEMORY).  Subclasses override only the steps they need; every
    default step implementation returns an empty dict so partial overrides
    are safe.

    Class variable ``spec`` must be defined by each concrete subclass.
    """

    # Subclasses MUST override this with a concrete AgentSpec instance.
    spec: AgentSpec  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _state_path(self) -> Path:
        return _STATE_DIR / f"{self.agent_id}_state.json"

    def _load_state(self) -> AgentState:
        """
        Load persisted agent state from the JSON file on disk.

        Returns a fresh AgentState if the file does not exist or cannot be
        parsed.
        """
        path = self._state_path()
        try:
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                return AgentState(
                    agent_id=raw.get("agent_id", self.agent_id),
                    open_tasks=raw.get("open_tasks", []),
                    decisions=raw.get("decisions", []),
                    errors=raw.get("errors", []),
                    metrics=raw.get("metrics", {}),
                    history=raw.get("history", []),
                )
        except Exception as exc:
            logger.warning("Could not load state for %s: %s", self.agent_id, exc)
        return AgentState(agent_id=self.agent_id)

    def _save_state(self, state: AgentState) -> None:
        """
        Persist agent state to disk as JSON.

        Silently swallows I/O errors so a state-write failure never crashes
        the agent.  History is trimmed to the last 50 entries before saving.
        """
        state.history = state.history[-50:]
        try:
            path = self._state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "agent_id": state.agent_id,
                        "open_tasks": state.open_tasks,
                        "decisions": state.decisions,
                        "errors": state.errors,
                        "metrics": state.metrics,
                        "history": state.history,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Could not save state for %s: %s", self.agent_id, exc)

    def _check_approval_required(self, action_type: str) -> bool:
        """
        Return True if the given action type must pass through ApprovalGate
        before being executed, according to this agent's spec.
        """
        return action_type in self.spec.requires_approval_for

    # ------------------------------------------------------------------
    # 7-step workflow — default step implementations (all return {})
    # ------------------------------------------------------------------

    async def observe(self, task: AgentTask, ctx: AgentContext) -> dict:
        """
        OBSERVE: gather inputs, retrieve a memory snapshot, and surface
        all relevant context for subsequent steps.

        Default implementation returns an empty dict; subclasses should
        override to query memory, read files, or call external sensors.
        """
        return {}

    async def analyze(
        self, task: AgentTask, ctx: AgentContext, observations: dict
    ) -> dict:
        """
        ANALYZE: identify patterns, risks, and opportunities based on
        the observations gathered in the OBSERVE step.

        Default implementation returns an empty dict.
        """
        return {}

    async def plan(
        self, task: AgentTask, ctx: AgentContext, analysis: dict
    ) -> dict:
        """
        PLAN: define concrete execution steps, resource requirements, and
        fallback options before any side-effecting work begins.

        Default implementation returns an empty dict.
        """
        return {}

    async def execute(
        self, task: AgentTask, ctx: AgentContext, plan: dict
    ) -> dict:
        """
        EXECUTE: call tools, dispatch sub-agents, and perform the work
        described in the plan.

        Default implementation returns an empty dict.  LEVEL_3 agents
        SHOULD override this to gate EXECUTE-class actions through
        ApprovalGate when ``_check_approval_required()`` returns True.
        """
        return {}

    async def verify(
        self, task: AgentTask, ctx: AgentContext, execution: dict
    ) -> dict:
        """
        VERIFY: inspect execution outputs for correctness, completeness,
        and policy compliance before reporting.

        Default implementation returns an empty dict.
        """
        return {}

    async def report(
        self, task: AgentTask, ctx: AgentContext, all_steps: dict[str, Any]
    ) -> StructuredOutput:
        """
        REPORT: synthesise all step data into a final StructuredOutput.

        Default implementation returns a SUCCESS output that bundles
        all step data into the ``data`` field.
        """
        return self._make_output(
            task=task,
            ctx=ctx,
            result="Workflow complete.",
            status=OutputStatus.SUCCESS,
            data={"workflow_steps": all_steps},
            confidence=self.spec.confidence_threshold,
        )

    async def save_memory(self, output: StructuredOutput, ctx: AgentContext) -> None:
        """
        SAVE_MEMORY: persist key facts from the completed workflow to the
        memory manager and update the agent's on-disk state.

        Default implementation records the task result in agent history.
        """
        state = self._load_state()
        state.history.append(
            {
                "task_id": output.task_id,
                "status": output.status.value,
                "result_snippet": output.result[:120],
                "timestamp": output.completed_at,
            }
        )
        self._save_state(state)

    # ------------------------------------------------------------------
    # Concrete run() — drives the 7-step workflow
    # ------------------------------------------------------------------

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """
        Execute the 7-step operational workflow.

        Step ordering: OBSERVE → ANALYZE → PLAN → EXECUTE → VERIFY →
        REPORT → SAVE_MEMORY.

        Each step is timed and a WorkflowResult is recorded.  If a step
        raises, the exception is caught, logged, and the step is recorded
        as "failed" — processing continues with the next step so that
        REPORT always executes.  SAVE_MEMORY runs after REPORT regardless
        of earlier failures.
        """
        results: dict[str, WorkflowResult] = {}
        step_data: dict[str, Any] = {}

        # ---- helper ----
        def _record(step: WorkflowStep, status: str, data: dict, t0: float) -> None:
            elapsed = (time.perf_counter() - t0) * 1000
            results[step.value] = WorkflowResult(
                step=step,
                status=status,
                data=data,
                duration_ms=round(elapsed, 2),
            )
            step_data[step.value] = data
            logger.debug(
                "Agent %s | step=%s | status=%s | %.1fms",
                self.agent_id, step.value, status, elapsed,
            )

        # ---- OBSERVE ----
        t0 = time.perf_counter()
        try:
            observations = await self.observe(task, ctx)
            _record(WorkflowStep.OBSERVE, "ok", observations, t0)
        except Exception as exc:
            logger.error("Agent %s observe error: %s", self.agent_id, exc)
            _record(WorkflowStep.OBSERVE, "failed", {"error": str(exc)}, t0)
            observations = {}

        # ---- ANALYZE ----
        t0 = time.perf_counter()
        try:
            analysis = await self.analyze(task, ctx, observations)
            _record(WorkflowStep.ANALYZE, "ok", analysis, t0)
        except Exception as exc:
            logger.error("Agent %s analyze error: %s", self.agent_id, exc)
            _record(WorkflowStep.ANALYZE, "failed", {"error": str(exc)}, t0)
            analysis = {}

        # ---- PLAN ----
        t0 = time.perf_counter()
        try:
            plan_data = await self.plan(task, ctx, analysis)
            _record(WorkflowStep.PLAN, "ok", plan_data, t0)
        except Exception as exc:
            logger.error("Agent %s plan error: %s", self.agent_id, exc)
            _record(WorkflowStep.PLAN, "failed", {"error": str(exc)}, t0)
            plan_data = {}

        # ---- EXECUTE ----
        t0 = time.perf_counter()
        try:
            execution = await self.execute(task, ctx, plan_data)
            _record(WorkflowStep.EXECUTE, "ok", execution, t0)
        except Exception as exc:
            logger.error("Agent %s execute error: %s", self.agent_id, exc)
            _record(WorkflowStep.EXECUTE, "failed", {"error": str(exc)}, t0)
            execution = {}

        # ---- VERIFY ----
        t0 = time.perf_counter()
        try:
            verification = await self.verify(task, ctx, execution)
            _record(WorkflowStep.VERIFY, "ok", verification, t0)
        except Exception as exc:
            logger.error("Agent %s verify error: %s", self.agent_id, exc)
            _record(WorkflowStep.VERIFY, "failed", {"error": str(exc)}, t0)

        # ---- REPORT (always runs) ----
        t0 = time.perf_counter()
        try:
            output = await self.report(task, ctx, step_data)
            _record(WorkflowStep.REPORT, "ok", {"result_snippet": output.result[:80]}, t0)
        except Exception as exc:
            logger.error("Agent %s report error: %s", self.agent_id, exc)
            _record(WorkflowStep.REPORT, "failed", {"error": str(exc)}, t0)
            output = StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=f"Report step failed: {exc}",
            )

        # Attach workflow step results to output data
        output.data["_workflow_results"] = {
            k: {
                "status": v.status,
                "duration_ms": v.duration_ms,
                "timestamp": v.timestamp,
            }
            for k, v in results.items()
        }

        # ---- SAVE_MEMORY (always runs, non-fatal) ----
        t0 = time.perf_counter()
        try:
            await self.save_memory(output, ctx)
            _record(WorkflowStep.SAVE_MEMORY, "ok", {}, t0)
        except Exception as exc:
            logger.warning("Agent %s save_memory error: %s", self.agent_id, exc)
            _record(WorkflowStep.SAVE_MEMORY, "failed", {"error": str(exc)}, t0)

        return output
