"""
Domain chief agents — specialized supervisors for specific knowledge domains.

Each chief owns a domain, has a tailored system prompt injected via the
PromptBuilder, and uses the full tool-use loop (web_search, code_exec, etc.).
"""
from __future__ import annotations

import logging

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)


class ResearchChief(BaseAgent):
    """
    Research domain chief.

    Uses web_search + memory_tool to ground responses in current facts.
    """

    agent_id = "research"
    model = "claude-opus-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            if not task.tools_allowed:
                task.tools_allowed = ["web_search", "memory_tool"]

            prompt = (
                "You are the Research Chief of the SOVEREIGN AI OS.\n\n"
                "Your specialisation: deep research, synthesis, citation, and analysis.\n\n"
                f"Research task:\n{task.objective}\n\n"
                "Approach:\n"
                "1. Use web_search to retrieve current information if needed\n"
                "2. Use memory_tool to recall prior research context\n"
                "3. Synthesise findings with source attribution\n"
                "4. Highlight key insights, contradictions, and knowledge gaps\n"
                "5. Provide an actionable conclusion\n\n"
                "Be thorough, precise, and cite sources where possible."
            )
            result, history = await self._call_with_tools(
                messages=[{"role": "user", "content": prompt}],
                ctx=ctx, task=task, max_tokens=4096,
            )
            return self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=0.85,
                data={"tool_turns": len(history)},
            )
        except Exception as exc:
            logger.error("ResearchChief failed: %s", exc)
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))


class FinanceChief(BaseAgent):
    """
    Finance domain chief.

    Uses code_exec for calculations + web_search for market data.
    All outputs require human review.
    """

    agent_id = "finance"
    model = "claude-opus-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            if not task.tools_allowed:
                task.tools_allowed = ["code_exec", "web_search", "memory_tool"]

            prompt = (
                "You are the Finance Chief of the SOVEREIGN AI OS.\n\n"
                "Your specialisation: financial analysis, budgeting, risk assessment,\n"
                "portfolio management, and macroeconomic context.\n\n"
                f"Finance task:\n{task.objective}\n\n"
                "Framework:\n"
                "1. Use code_exec for numerical calculations, projections, and modelling\n"
                "2. Use web_search for current market data, rates, and economic context\n"
                "3. Quantify the financial dimensions (amounts, rates, timeframes)\n"
                "4. Assess risk (probability × impact)\n"
                "5. Identify alternatives with trade-offs\n"
                "6. Provide a clear recommendation with rationale\n"
                "7. Flag any items requiring human approval\n\n"
                "Be precise with numbers. Flag uncertainty explicitly.\n"
                "IMPORTANT: Never execute financial transactions — only analyse and advise."
            )
            result, history = await self._call_with_tools(
                messages=[{"role": "user", "content": prompt}],
                ctx=ctx, task=task, max_tokens=3000,
            )
            out = self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=0.82,
                data={"tool_turns": len(history)},
            )
            out.requires_human_review = True
            return out
        except Exception as exc:
            logger.error("FinanceChief failed: %s", exc)
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))


class ContentChief(BaseAgent):
    """
    Content domain chief.

    Uses memory_tool for brand voice context + web_search for trends.
    """

    agent_id = "content"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            if not task.tools_allowed:
                task.tools_allowed = ["memory_tool", "web_search"]

            prompt = (
                "You are the Content Chief of the SOVEREIGN AI OS.\n\n"
                "Your specialisation: content strategy, copywriting, brand voice,\n"
                "email drafting, social media, and editorial planning.\n\n"
                f"Content task:\n{task.objective}\n\n"
                "Approach:\n"
                "1. Use memory_tool to retrieve brand voice, style guides, past content\n"
                "2. Use web_search for trends and competitor context if relevant\n"
                "3. Deliver high-quality, publication-ready copy\n"
                "4. Match the correct tone for the specified audience and channel\n"
                "5. Apply SEO awareness where relevant\n"
                "6. Structure with clear headings and CTAs where appropriate\n\n"
                "Match the brand voice from memory context if available."
            )
            result, history = await self._call_with_tools(
                messages=[{"role": "user", "content": prompt}],
                ctx=ctx, task=task, max_tokens=3000,
            )
            return self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=0.80,
                data={"tool_turns": len(history)},
            )
        except Exception as exc:
            logger.error("ContentChief failed: %s", exc)
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))


class LegalChief(BaseAgent):
    """
    Legal / compliance domain chief.

    Uses web_search for statute/regulation lookup.
    All outputs require human review — NOT legal advice.
    """

    agent_id = "legal"
    model = "claude-opus-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            if not task.tools_allowed:
                task.tools_allowed = ["web_search", "memory_tool"]

            prompt = (
                "You are the Legal Chief of the SOVEREIGN AI OS.\n\n"
                "Your specialisation: legal research, contract analysis, compliance\n"
                "checking, and regulatory guidance.\n\n"
                f"Legal task:\n{task.objective}\n\n"
                "Framework:\n"
                "1. Use web_search to look up relevant statutes, regulations, and case law\n"
                "2. Use memory_tool to recall prior legal context and decisions\n"
                "3. Identify the legal/regulatory area (contract law, GDPR, etc.)\n"
                "4. Summarise applicable rules or precedents\n"
                "5. Highlight risks and red flags\n"
                "6. Suggest practical next steps\n"
                "7. Recommend professional counsel for binding decisions\n\n"
                "IMPORTANT DISCLAIMER: This is AI-generated legal information, NOT\n"
                "legal advice. Always consult a qualified attorney for binding matters."
            )
            result, history = await self._call_with_tools(
                messages=[{"role": "user", "content": prompt}],
                ctx=ctx, task=task, max_tokens=3000,
            )
            out = self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=0.75,
                data={"tool_turns": len(history)},
            )
            out.requires_human_review = True
            return out
        except Exception as exc:
            logger.error("LegalChief failed: %s", exc)
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))
