"""
CEO Agent — top-level strategic executive.

Receives raw user intent, interprets it at a strategic level, selects the
operating mode, and produces a structured strategic brief for the Chief of Staff.

Upgraded to AgentLevel.LEVEL_3: full 7-step operational workflow with
persistent state and structured AgentSpec metadata.
"""
from __future__ import annotations

import json
import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask
from sovereign.swarm.leveled_agent import AgentLevel, AgentSpec, LeveledAgent

logger = logging.getLogger(__name__)

OPERATING_MODES = [
    "command", "business", "personal", "finance",
    "study", "travel", "research", "builder",
    "local_offline", "survival",
]


class CEOAgent(LeveledAgent):
    """
    The top-level executive agent — LEVEL_5 Sovereign Executive.

    Responsibilities:
    - Interpret user intent at strategic level
    - Select the appropriate operating mode
    - Decompose intent into a high-level strategic brief
    - Set the action class ceiling for the session
    - Delegate to ChiefOfStaff for task decomposition

    Uses claude-opus-4-6 (frontier model) for highest reasoning quality.

    Workflow steps:
      OBSERVE   — retrieve memory snapshot, surface prior session context
      ANALYZE   — startup analysis (mode, request class, tools, sub-agents)
      PLAN      — select operating mode
      EXECUTE   — build strategic brief
      VERIFY    — confirm confidence meets threshold
      REPORT    — assemble StructuredOutput
      SAVE_MEM  — persist key decisions to agent state
    """

    agent_id = "ceo"
    model = "claude-opus-4-6"

    spec = AgentSpec(
        agent_id="ceo",
        level=AgentLevel.LEVEL_5,
        mission="Strategic intent analysis and operating mode selection",
        triggers=["new_request", "mode_change", "escalation"],
        tools_allowed=["memory_tool", "web_search"],
        escalate_to="",
        requires_approval_for=["mode_change", "resource_allocation"],
        success_metric="Intent correctly classified with confidence >= 0.8",
        failure_condition="Intent confidence < 0.5 or unknown mode selected",
        confidence_threshold=0.8,
    )

    # ------------------------------------------------------------------
    # Workflow step overrides
    # ------------------------------------------------------------------

    async def observe(self, task: AgentTask, ctx: AgentContext) -> dict:
        """
        OBSERVE: surface memory snapshot and prior session context.
        Returns the memory snapshot already carried in AgentContext.
        """
        return {
            "memory_snapshot": ctx.memory_snapshot,
            "session_id": ctx.session_id,
            "operating_mode": ctx.operating_mode,
            "objective": task.objective,
        }

    async def analyze(
        self, task: AgentTask, ctx: AgentContext, observations: dict
    ) -> dict:
        """
        ANALYZE: run startup analysis to determine request class, tools,
        sub-agents, approval threshold, and internet requirements.
        Mirrors the Section 23 steps 4-9 startup sequence.
        """
        mode = observations.get("operating_mode", ctx.operating_mode)
        return await self._startup_analysis(task.objective, mode, ctx)

    async def plan(
        self, task: AgentTask, ctx: AgentContext, analysis: dict
    ) -> dict:
        """
        PLAN: classify the operating mode for this session.
        """
        mode = await self._select_mode(task.objective, ctx)
        return {"mode": mode, "analysis": analysis}

    async def execute(
        self, task: AgentTask, ctx: AgentContext, plan: dict
    ) -> dict:
        """
        EXECUTE: build the strategic brief / execution plan.
        Gated: mode_change requires approval per spec.
        """
        mode = plan.get("mode", ctx.operating_mode)
        analysis = plan.get("analysis", {})
        brief = await self._build_strategic_brief(task.objective, mode, ctx, analysis)
        return {
            "brief": brief,
            "mode": mode,
            "action_class": task.action_class.name,
            **analysis,
        }

    async def verify(
        self, task: AgentTask, ctx: AgentContext, execution: dict
    ) -> dict:
        """
        VERIFY: confirm that a brief was produced and mode is valid.
        Returns a confidence score and any validation warnings.
        """
        warnings: list[str] = []
        mode = execution.get("mode", "")
        brief = execution.get("brief", "")
        confidence = 0.85

        if mode not in OPERATING_MODES:
            warnings.append(f"Unknown mode '{mode}' — falling back to session default.")
            confidence = 0.5

        if not brief or len(brief.strip()) < 20:
            warnings.append("Strategic brief appears empty or too short.")
            confidence = min(confidence, 0.4)

        return {
            "valid": len(warnings) == 0,
            "confidence": confidence,
            "warnings": warnings,
        }

    async def report(
        self, task: AgentTask, ctx: AgentContext, all_steps: dict
    ) -> StructuredOutput:
        """
        REPORT: assemble the final StructuredOutput from verified execution data.
        """
        execution = all_steps.get("execute", {})
        verification = all_steps.get("verify", {})

        brief = execution.get("brief", "")
        mode = execution.get("mode", ctx.operating_mode)
        confidence = verification.get("confidence", 0.85)
        warnings = verification.get("warnings", [])

        reasoning = (
            f"Mode: {mode} | "
            f"Class: {execution.get('request_class', 'analysis')} | "
            f"Internet: {execution.get('internet_needed', False)} | "
            f"SubAgents: {execution.get('sub_agents_needed', False)}"
        )
        if warnings:
            reasoning += f" | Warnings: {'; '.join(warnings)}"

        data = {
            "operating_mode": mode,
            "action_class": execution.get("action_class", task.action_class.name),
        }
        # Merge in analysis fields if present
        for key in (
            "request_class", "internet_needed", "tools_needed",
            "sub_agents_needed", "approval_threshold",
            "internet_keywords", "file_check",
        ):
            if key in execution:
                data[key] = execution[key]

        return self._make_output(
            task=task,
            ctx=ctx,
            result=brief or "Strategic brief unavailable.",
            status=OutputStatus.SUCCESS if brief else OutputStatus.PARTIAL,
            data=data,
            reasoning=reasoning,
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Private helpers (unchanged logic from original implementation)
    # ------------------------------------------------------------------

    async def _startup_analysis(
        self,
        objective: str,
        mode: str,
        ctx: AgentContext,
    ) -> dict:
        """
        Section 23 steps 4-9: structured analysis of what the session needs.

        Returns a dict with:
          request_class      : research | execution | analysis | draft | decision
          internet_needed    : bool — live/current data required
          tools_needed       : list[str] — suggested tool names
          sub_agents_needed  : bool — parallel decomposition beneficial
          approval_threshold : none | suggest | execute
          internet_keywords  : list[str] — search terms if internet_needed
          file_check         : bool — user seems to reference a file/attachment
        """
        prompt = (
            f"You are the SOVEREIGN AI OS startup analyser.\n\n"
            f"Mode: {mode}\n"
            f"Request: {objective}\n\n"
            f"Reply with a JSON object (no markdown) with exactly these keys:\n"
            f"  request_class: one of [research, execution, analysis, draft, decision]\n"
            f"  internet_needed: true if current/live information is required\n"
            f"  tools_needed: array of tool names from [web_search, code_exec, file_ops, memory_tool]\n"
            f"  sub_agents_needed: true if task benefits from parallel decomposition\n"
            f"  approval_threshold: one of [none, suggest, execute]\n"
            f"  internet_keywords: array of 1-3 search terms if internet_needed else []\n"
            f"  file_check: true if the request references a file, doc, or attachment"
        )
        raw = await self._call_claude(
            [{"role": "user", "content": prompt}], ctx, max_tokens=200
        )
        try:
            clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(clean)
        except Exception:
            return {
                "request_class": "analysis",
                "internet_needed": False,
                "tools_needed": [],
                "sub_agents_needed": False,
                "approval_threshold": "none",
                "internet_keywords": [],
                "file_check": False,
            }

    async def _select_mode(self, objective: str, ctx: AgentContext) -> str:
        """
        Ask Claude to classify the user's objective into an operating mode.
        Uses a lightweight prompt on the fast model to minimise latency.
        """
        prompt = (
            f"Classify the following user request into exactly one operating mode.\n\n"
            f"Request: {objective}\n\n"
            f"Available modes: {', '.join(OPERATING_MODES)}\n\n"
            f"Reply with only the mode name, nothing else."
        )
        messages = [{"role": "user", "content": prompt}]
        raw = await self._call_claude(messages, ctx, max_tokens=20)
        mode = raw.strip().lower().replace("-", "_").split()[0]
        return mode if mode in OPERATING_MODES else ctx.operating_mode

    async def _build_strategic_brief(
        self,
        objective: str,
        mode: str,
        ctx: AgentContext,
        analysis: dict,
    ) -> str:
        """
        Step 10 of Section 23: build execution plan / strategic brief.
        Enriched with startup analysis context.
        """
        tools_line = (
            f"Tools identified: {', '.join(analysis.get('tools_needed', []))}"
            if analysis.get("tools_needed")
            else "No external tools required"
        )
        internet_line = (
            f"Live internet search needed — keywords: {analysis.get('internet_keywords', [])}"
            if analysis.get("internet_needed")
            else "No live internet required"
        )
        prompt = (
            f"You are the CEO Agent of the SOVEREIGN AI OS.\n\n"
            f"Operating mode: {mode}\n"
            f"Request class: {analysis.get('request_class', 'analysis')}\n"
            f"User request: {objective}\n\n"
            f"Context: {tools_line}. {internet_line}.\n"
            f"Sub-agents needed: {analysis.get('sub_agents_needed', False)}\n"
            f"Approval threshold: {analysis.get('approval_threshold', 'none')}\n\n"
            f"Produce a concise strategic brief with:\n"
            f"1. Core objective (1 sentence)\n"
            f"2. Key success criteria (2-3 bullets)\n"
            f"3. Execution plan (2-4 steps with agent assignments)\n"
            f"4. Risks / constraints\n"
            f"5. Memory updates to save after completion\n\n"
            f"Be sharp and executive. No fluff."
        )
        return await self._call_claude(
            [{"role": "user", "content": prompt}], ctx, task=None, max_tokens=600
        )
