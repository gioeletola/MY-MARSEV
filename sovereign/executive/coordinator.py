"""Coordinator — routes tasks from Chief of Staff to the best available agent."""
from __future__ import annotations

import logging
from typing import Any

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Standalone Coordinator (no BaseAgent dependency — usable without full DI)
# ---------------------------------------------------------------------------

_FALLBACK_AGENT_ID = "worker"


class Coordinator:
    """
    Lightweight routing engine that maps tasks to agent IDs.

    Resolution order:
      1. Explicit ``agent_hint`` in task dict.
      2. Keyword match against task ``objective``.
      3. Fallback to ``worker`` agent.
    """

    _KEYWORD_ROUTES: dict[str, str] = {
        # Finance
        "finance": "finance_os_chief",
        "invest": "portfolio_manager",
        "budget": "budget_manager",
        "expense": "expense_tracker",
        "tax": "tax_strategist",
        "invoice": "invoice_chaser",
        "payment": "payment_processor",
        "net worth": "net_worth_calculator",
        # Code / Engineering
        "code": "codebridge_chief",
        "build": "app_builder",
        "test": "qa_testing",
        "deploy": "devops_architect",
        "debug": "codebridge_chief",
        "api": "codebridge_chief",
        "database": "data_engineer",
        # Research
        "research": "research_centre_chief",
        "search": "web_analyst",
        "analyze": "research_centre_chief",
        "report": "research_centre_chief",
        "summarize": "content_writer",
        "summarise": "content_writer",
        # Calendar / Scheduling
        "calendar": "smart_calendar",
        "schedule": "smart_calendar",
        "meeting": "smart_calendar",
        "appointment": "smart_calendar",
        "remind": "reminder_sender",
        # Communication
        "email": "inbox_manager",
        "write": "content_writer",
        "draft": "content_writer",
        "message": "inbox_manager",
        "reply": "inbox_manager",
        # Personal / Health
        "habit": "habit_engineer",
        "health": "energy_manager",
        "fitness": "energy_manager",
        "sleep": "energy_manager",
        "journal": "journal_logger",
        "mood": "journal_logger",
        # Memory / Knowledge
        "memory": "personal_archivist",
        "note": "personal_archivist",
        "archive": "personal_archivist",
        "bookmark": "personal_archivist",
        # Security
        "security": "security_sentinel",
        "threat": "security_sentinel",
        "vulnerability": "security_sentinel",
        "password": "security_sentinel",
        "incident": "incident_response",
        # Legal / Compliance
        "legal": "legal_ops_chief",
        "contract": "legal_ops_chief",
        "compliance": "legal_ops_chief",
        "risk": "legal_ops_chief",
        # CRM / Business
        "crm": "crm_chief",
        "client": "crm_chief",
        "customer": "crm_chief",
        "lead": "crm_chief",
        "sales": "crm_chief",
        # Marketing / Content
        "marketing": "marketing_chief",
        "campaign": "marketing_chief",
        "social": "social_media_manager",
        "content": "content_writer",
        "blog": "content_writer",
        "seo": "seo_specialist",
        # HR / People
        "hr": "hr_chief",
        "hire": "hr_chief",
        "recruit": "hr_chief",
        "team": "hr_chief",
        # Strategy / Decision
        "strategy": "imperial_commander",
        "decision": "option_generator",
        "option": "option_generator",
        "plan": "chief_of_staff",
        "goal": "chief_of_staff",
        # Data / Analytics
        "data": "bi_chief",
        "analytics": "bi_chief",
        "dashboard": "bi_chief",
        "metric": "bi_chief",
        "kpi": "bi_chief",
        # Media / Content production
        "video": "media_chief",
        "podcast": "media_chief",
        "thumbnail": "thumbnail_brief",
        "publish": "publishing_queue",
        # Travel / Errand
        "travel": "travel_planner",
        "flight": "travel_planner",
        "hotel": "travel_planner",
        "errand": "errand_coordinator",
        "grocery": "grocery_tracker",
        # Offline / Local
        "offline": "offline_assistant",
        "local": "offline_assistant",
    }

    def __init__(self) -> None:
        self._logger = logging.getLogger("coordinator.router")

    async def route(
        self,
        task: dict[str, Any],
        agent_registry: Any = None,
    ) -> dict[str, Any]:
        """
        Route a single task dict to the best agent.

        Args:
            task: dict with keys: objective (str), agent_hint (str|None),
                  priority (int|None), dependencies (list|None).
            agent_registry: Optional registry with ``get(agent_id)`` method
                            used to validate that the target agent exists.

        Returns:
            dict with: agent_id (str), center_id (str|None),
                       confidence (float), reasoning (str).
        """
        objective: str = task.get("objective", "")
        hint: str = task.get("agent_hint", "") or ""

        # 1. Try explicit agent_hint
        if hint:
            if agent_registry is None or self._agent_exists(agent_registry, hint):
                return self._decision(hint, 0.95, f"Explicit agent_hint '{hint}' used directly.")
            # hint provided but not in registry — log and fall through
            self._logger.warning(
                "Coordinator: agent_hint '%s' not found in registry, falling back to keyword match.",
                hint,
            )

        # 2. Keyword match on objective
        agent_id, keyword = self._keyword_match(objective)
        if agent_id:
            if agent_registry is None or self._agent_exists(agent_registry, agent_id):
                return self._decision(
                    agent_id,
                    0.80,
                    f"Keyword '{keyword}' matched agent '{agent_id}' from objective.",
                )
            # matched agent not in registry — fall through to fallback
            self._logger.warning(
                "Coordinator: keyword-matched agent '%s' not in registry, using fallback.",
                agent_id,
            )

        # 3. Fallback
        return self._decision(
            _FALLBACK_AGENT_ID,
            0.40,
            "No agent_hint or keyword match found; routed to fallback worker.",
        )

    async def route_all(
        self,
        tasks: list[dict[str, Any]],
        agent_registry: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Route all tasks and return a list of routing decisions (same order as input).
        """
        results = []
        for task in tasks:
            decision = await self.route(task, agent_registry=agent_registry)
            decision["task_id"] = task.get("task_id", "")
            decision["objective"] = task.get("objective", "")
            results.append(decision)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _keyword_match(self, objective: str) -> tuple[str, str]:
        """
        Scan the objective string for known keywords.
        Returns (agent_id, matched_keyword) or ("", "") if no match.
        Longer keywords take priority over shorter ones (most-specific-first).
        """
        obj_lower = objective.lower()
        # Sort by keyword length descending so multi-word keys match before substrings
        for keyword in sorted(self._KEYWORD_ROUTES, key=len, reverse=True):
            if keyword in obj_lower:
                return self._KEYWORD_ROUTES[keyword], keyword
        return "", ""

    @staticmethod
    def _agent_exists(agent_registry: Any, agent_id: str) -> bool:
        """Return True if agent_registry can confirm the agent exists."""
        try:
            result = agent_registry.get(agent_id)
            return result is not None
        except Exception:
            return False

    @staticmethod
    def _decision(
        agent_id: str,
        confidence: float,
        reasoning: str,
        center_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "center_id": center_id,
            "confidence": confidence,
            "reasoning": reasoning,
        }


# ---------------------------------------------------------------------------
# CoordinatorAgent — BaseAgent wrapper used by the orchestrator
# ---------------------------------------------------------------------------


class CoordinatorAgent(BaseAgent):
    """Routes tasks to the appropriate chief or worker agents."""

    agent_id = "coordinator"
    model = "claude-sonnet-4-6"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._router = Coordinator()

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """Determine which agent should handle the task using Coordinator routing."""
        try:
            task_dict = {
                "objective": task.objective,
                "agent_hint": task.context.get("agent_hint", ""),
                "priority": task.context.get("priority", 3),
                "dependencies": task.context.get("dependencies", []),
                "task_id": task.task_id,
            }
            decision = await self._router.route(task_dict)
            agent_id = decision["agent_id"]
            confidence = decision["confidence"]
            reasoning = decision["reasoning"]

            self._logger.debug(
                "CoordinatorAgent: task '%s' → agent '%s' (confidence=%.2f)",
                task.objective[:60],
                agent_id,
                confidence,
            )

            return self._make_output(
                task=task,
                ctx=ctx,
                result=f"Task routed to: {agent_id}",
                status=OutputStatus.SUCCESS,
                data={
                    "routed_to": agent_id,
                    "center_id": decision.get("center_id"),
                    "confidence": confidence,
                    "reasoning": reasoning,
                },
                reasoning=reasoning,
                confidence=confidence,
            )
        except Exception as exc:
            return StructuredOutput.failure(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                error=str(exc),
            )

    @property
    def _logger(self) -> logging.Logger:  # type: ignore[override]
        return logging.getLogger(f"agent.{self.agent_id}")
