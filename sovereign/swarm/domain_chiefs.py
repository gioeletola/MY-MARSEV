"""
Domain chief agents — specialized supervisors for specific knowledge domains.

Each chief owns a domain, has a tailored system prompt injected via the
PromptBuilder, and can spawn domain-specific worker agents.
"""
from __future__ import annotations

import logging

from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.output.output_contract import OutputStatus, StructuredOutput

logger = logging.getLogger(__name__)


class ResearchChief(BaseAgent):
    """
    Research domain chief.

    Specialises in deep research, synthesis, citations, analysis,
    competitive intelligence, and knowledge consolidation.
    Uses web search and memory tools to ground responses in facts.
    """

    agent_id = "research"
    model = "claude-opus-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            prompt = (
                "You are the Research Chief of the SOVEREIGN AI OS.\n\n"
                "Your specialisation: deep research, synthesis, citation, and analysis.\n\n"
                f"Research task:\n{task.objective}\n\n"
                "Approach:\n"
                "1. Identify the core research question\n"
                "2. Retrieve relevant information (use web_search if available)\n"
                "3. Synthesise findings with source attribution\n"
                "4. Highlight key insights, contradictions, and knowledge gaps\n"
                "5. Provide an actionable conclusion\n\n"
                "Be thorough, precise, and cite sources where possible."
            )
            result = await self._call_claude(
                messages=[{"role": "user", "content": prompt}],
                ctx=ctx, task=task, max_tokens=4096,
            )
            return self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=0.85,
            )
        except Exception as exc:
            logger.error("ResearchChief failed", error=str(exc))
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))


class FinanceChief(BaseAgent):
    """
    Finance domain chief.

    Specialises in financial analysis, budgeting, cashflow, portfolio
    review, macroeconomic context, and financial decision support.
    All EXECUTE-class actions require explicit approval.
    """

    agent_id = "finance"
    model = "claude-opus-4-6"   # Frontier model — financial decisions are high-stakes

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            prompt = (
                "You are the Finance Chief of the SOVEREIGN AI OS.\n\n"
                "Your specialisation: financial analysis, budgeting, risk assessment,\n"
                "portfolio management, and macroeconomic context.\n\n"
                f"Finance task:\n{task.objective}\n\n"
                "Framework:\n"
                "1. Quantify the financial dimensions (amounts, rates, timeframes)\n"
                "2. Assess risk (probability × impact)\n"
                "3. Identify alternatives with trade-offs\n"
                "4. Provide a clear recommendation with rationale\n"
                "5. Flag any items requiring human approval\n\n"
                "Be precise with numbers. Flag uncertainty explicitly.\n"
                "IMPORTANT: Never execute financial transactions — only analyse and advise."
            )
            result = await self._call_claude(
                messages=[{"role": "user", "content": prompt}],
                ctx=ctx, task=task, max_tokens=3000,
            )
            return self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=0.82,
                requires_human_review=True,   # Finance outputs always flagged for review
            )
        except Exception as exc:
            logger.error("FinanceChief failed", error=str(exc))
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))

    def _make_output(self, *, requires_human_review: bool = False, **kwargs):  # type: ignore[override]
        out = super()._make_output(**kwargs)
        out.requires_human_review = True   # Always flag finance outputs
        return out


class ContentChief(BaseAgent):
    """
    Content domain chief.

    Specialises in content strategy, copywriting, social media,
    email drafting, SEO, brand voice, and content calendars.
    """

    agent_id = "content"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            prompt = (
                "You are the Content Chief of the SOVEREIGN AI OS.\n\n"
                "Your specialisation: content strategy, copywriting, brand voice,\n"
                "email drafting, social media, and editorial planning.\n\n"
                f"Content task:\n{task.objective}\n\n"
                "Deliver:\n"
                "- High-quality, publication-ready copy\n"
                "- Correct tone for the specified audience and channel\n"
                "- SEO-aware where relevant\n"
                "- Structured with clear headings and CTAs where appropriate\n\n"
                "Match the brand voice from memory context if available."
            )
            result = await self._call_claude(
                messages=[{"role": "user", "content": prompt}],
                ctx=ctx, task=task, max_tokens=3000,
            )
            return self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=0.80,
            )
        except Exception as exc:
            logger.error("ContentChief failed", error=str(exc))
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))


class LegalChief(BaseAgent):
    """
    Legal / compliance domain chief.

    Provides legal research, contract review, compliance checks,
    and regulatory guidance. NOT legal advice — always recommend
    qualified counsel for binding decisions.
    """

    agent_id = "legal"
    model = "claude-opus-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            prompt = (
                "You are the Legal Chief of the SOVEREIGN AI OS.\n\n"
                "Your specialisation: legal research, contract analysis, compliance\n"
                "checking, and regulatory guidance.\n\n"
                f"Legal task:\n{task.objective}\n\n"
                "Framework:\n"
                "1. Identify the legal/regulatory area (contract law, GDPR, etc.)\n"
                "2. Summarise applicable rules or precedents\n"
                "3. Highlight risks and red flags\n"
                "4. Suggest practical next steps\n"
                "5. Recommend professional counsel for binding decisions\n\n"
                "IMPORTANT DISCLAIMER: This is AI-generated legal information, NOT\n"
                "legal advice. Always consult a qualified attorney for binding matters."
            )
            result = await self._call_claude(
                messages=[{"role": "user", "content": prompt}],
                ctx=ctx, task=task, max_tokens=3000,
            )
            out = self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=0.75,
            )
            out.requires_human_review = True
            return out
        except Exception as exc:
            logger.error("LegalChief failed", error=str(exc))
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))
