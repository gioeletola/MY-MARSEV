"""
Executive Assistant Agent — second top-level agent after CEO.

Translates strategic objectives into actionable tasks, briefings, agenda,
follow-ups, and approval workflows. Acts as the operational bridge between
the CEO's vision and the Chief of Staff's execution layer.
"""
from __future__ import annotations

import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)


class ExecutiveAssistantAgent(BaseAgent):
    """
    Executive Assistant — translates CEO vision into operational structure.

    Responsibilities:
    - Convert goals into time-bounded tasks with owners and deadlines
    - Maintain the approval inbox and surface items needing human decision
    - Prepare briefings, agendas, meeting prep, and follow-up summaries
    - Track open loops, commitments, and pending items
    - Route urgent items to the appropriate chief or approval gate
    """

    agent_id = "executive_assistant"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            if not task.tools_allowed:
                task.tools_allowed = ["memory_tool", "web_search"]

            intent = task.context.get("intent", "general")
            handler = {
                "briefing":    self._briefing,
                "agenda":      self._agenda,
                "follow_up":   self._follow_up,
                "approval":    self._approval_prep,
                "task_list":   self._task_list,
            }.get(intent, self._general)

            result, history = await handler(task, ctx)
            return self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=0.88,
                data={"intent": intent, "tool_turns": len(history)},
            )
        except Exception as exc:
            logger.error("ExecutiveAssistantAgent failed: %s", exc)
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))

    async def _general(self, task, ctx):
        prompt = (
            "You are the Executive Assistant of the SOVEREIGN AI OS.\n\n"
            "Your role: translate the CEO's objectives into clear, actionable operational structure.\n\n"
            f"Request:\n{task.objective}\n\n"
            "Deliver:\n"
            "1. Parsed objective (what exactly needs to happen)\n"
            "2. Task breakdown with owners, priorities, and deadlines\n"
            "3. Dependencies and blockers\n"
            "4. Items requiring human approval (flag explicitly)\n"
            "5. Follow-up reminders to schedule\n\n"
            "Be precise, structured, and executive-grade. No fluff."
        )
        return await self._call_with_tools([{"role": "user", "content": prompt}], ctx, task)

    async def _briefing(self, task, ctx):
        prompt = (
            "You are the Executive Assistant preparing a briefing document.\n\n"
            f"Topic: {task.objective}\n\n"
            "Briefing structure:\n"
            "- Situation summary (2-3 sentences)\n"
            "- Key facts and context\n"
            "- What decision or action is needed\n"
            "- Options available\n"
            "- Recommended next step\n"
            "- Risk / downside\n"
            "- Deadline"
        )
        return await self._call_with_tools([{"role": "user", "content": prompt}], ctx, task)

    async def _agenda(self, task, ctx):
        prompt = (
            "You are the Executive Assistant building a structured agenda.\n\n"
            f"Context: {task.objective}\n\n"
            "Build a time-blocked agenda with:\n"
            "- Priority items first (with estimated time)\n"
            "- Decisions to make\n"
            "- Reviews needed\n"
            "- Communications to send\n"
            "- Delegations to assign\n"
            "- Buffer time for interruptions"
        )
        return await self._call_with_tools([{"role": "user", "content": prompt}], ctx, task)

    async def _follow_up(self, task, ctx):
        prompt = (
            "You are the Executive Assistant managing follow-ups.\n\n"
            f"Context: {task.objective}\n\n"
            "Produce:\n"
            "- Summary of what was decided / agreed\n"
            "- Action items with owners and deadlines\n"
            "- Items to monitor\n"
            "- Next review checkpoint\n"
            "- Escalation triggers"
        )
        return await self._call_with_tools([{"role": "user", "content": prompt}], ctx, task)

    async def _approval_prep(self, task, ctx):
        prompt = (
            "You are the Executive Assistant preparing an approval request.\n\n"
            f"Item requiring approval: {task.objective}\n\n"
            "Approval brief format:\n"
            "1. Decision title\n"
            "2. Context and background\n"
            "3. What is being requested\n"
            "4. Options considered\n"
            "5. Recommended option\n"
            "6. Risk if approved / if rejected\n"
            "7. Cost / resource implications\n"
            "8. Reversibility\n"
            "9. Deadline for decision\n"
            "10. What happens if delayed\n\n"
            "Flag as REQUIRES_HUMAN_APPROVAL."
        )
        result = await self._call_with_tools([{"role": "user", "content": prompt}], ctx, task)
        return result

    async def _task_list(self, task, ctx):
        prompt = (
            "You are the Executive Assistant converting goals into structured tasks.\n\n"
            f"Goal: {task.objective}\n\n"
            "Produce a task list with:\n"
            "- Task name\n"
            "- Owner (agent or human)\n"
            "- Priority (P1/P2/P3)\n"
            "- Deadline\n"
            "- Dependencies\n"
            "- Success criteria\n"
            "- Action class (READ/SUGGEST/DRAFT/EXECUTE)\n\n"
            "Format as a clean numbered list."
        )
        return await self._call_with_tools([{"role": "user", "content": prompt}], ctx, task)
