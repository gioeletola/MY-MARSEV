"""
CEO Agent — top-level strategic executive.

Receives raw user intent, interprets it at a strategic level, selects the
operating mode, and produces a structured strategic brief for the Chief of Staff.
"""
from __future__ import annotations

import json
import logging

from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.kernel.action_classes import ActionClass
from sovereign.output.output_contract import OutputStatus, StructuredOutput

logger = logging.getLogger(__name__)

OPERATING_MODES = [
    "command", "business", "personal", "finance",
    "study", "travel", "research", "builder",
    "local_offline", "survival",
]


class CEOAgent(BaseAgent):
    """
    The top-level executive agent.

    Responsibilities:
    - Interpret user intent at strategic level
    - Select the appropriate operating mode
    - Decompose intent into a high-level strategic brief
    - Set the action class ceiling for the session
    - Delegate to ChiefOfStaff for task decomposition

    Uses claude-opus-4-6 (frontier model) for highest reasoning quality.
    """

    agent_id = "ceo"
    model = "claude-opus-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """
        Process a user request as the CEO.

        Implements the Section 23 startup sequence (13 steps):
        1-2.  Classify request + detect mode
        3.    Memory retrieval (orchestrator handles this before CEO runs)
        4-9.  File check, internet freshness, tools, sub-agents, approval threshold → startup_analysis
        10.   Build strategic brief (execution plan)
        11-13.Execute/draft + summarize + propose memory updates (downstream)

        Returns a StructuredOutput with:
          result:  The strategic brief text
          data:    startup analysis + operating_mode + action_class
        """
        try:
            # Steps 1-2: classify + detect mode
            mode = await self._select_mode(task.objective, ctx)
            # Steps 4-9: startup analysis (internet, tools, sub-agents, approval, class)
            analysis = await self._startup_analysis(task.objective, mode, ctx)
            # Step 10: strategic brief / execution plan
            brief = await self._build_strategic_brief(task.objective, mode, ctx, analysis)

            return self._make_output(
                task=task,
                ctx=ctx,
                result=brief,
                status=OutputStatus.SUCCESS,
                data={
                    "operating_mode": mode,
                    "action_class": task.action_class.name,
                    **analysis,
                },
                reasoning=f"Mode: {mode} | Class: {analysis.get('request_class')} | "
                          f"Internet: {analysis.get('internet_needed')} | "
                          f"SubAgents: {analysis.get('sub_agents_needed')}",
                confidence=0.85,
            )
        except Exception as exc:
            logger.error("CEOAgent failed: %s", exc)
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
            )

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
            # Strip markdown fences if present
            clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(clean)
        except Exception:
            # Safe defaults
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
