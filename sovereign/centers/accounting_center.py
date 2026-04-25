"""
Accounting Center — finance operations, cashflow, budgets, expenses, and tax.
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.swarm.base_agent import AgentContext, AgentTask

logger = logging.getLogger(__name__)

CENTER_ID = "accounting_centre"
DESCRIPTION = "Accounting & Finance Operations"
REQUIRES_REVIEW = True
AGENTS = [
    "finance_ops_chief",
    "cashflow_analyst",
    "budget_manager",
    "expense_tracker",
    "tax_optimizer",
]


class AccountingCenter:
    """
    Coordinates accounting and finance operations agents: cashflow analysis,
    budget management, expense tracking, and tax optimization.

    Requires human review before any financial outputs are acted upon.
    Used by the orchestrator to route accounting and finance requests to
    the appropriate agent without knowing individual IDs.
    """

    DOMAIN_MAP: dict[str, str] = {
        "accounting": "finance_ops_chief",
        "finance": "finance_ops_chief",
        "financial": "finance_ops_chief",
        "cashflow": "cashflow_analyst",
        "cash": "cashflow_analyst",
        "liquidity": "cashflow_analyst",
        "budget": "budget_manager",
        "budgets": "budget_manager",
        "budgeting": "budget_manager",
        "expense": "expense_tracker",
        "expenses": "expense_tracker",
        "spending": "expense_tracker",
        "tax": "tax_optimizer",
        "taxes": "tax_optimizer",
        "taxation": "tax_optimizer",
    }

    def __init__(self, agent_registry: Any) -> None:
        self._registry = agent_registry

    def route(self, intent_keywords: list[str]) -> str:
        """Return the most appropriate accounting agent_id for the given intent keywords."""
        for kw in intent_keywords:
            if kw.lower() in self.DOMAIN_MAP:
                return self.DOMAIN_MAP[kw.lower()]
        return "finance_ops_chief"

    async def dispatch(
        self,
        task: AgentTask,
        ctx: AgentContext,
        intent_keywords: list[str] | None = None,
    ):
        """Route and execute a task through the appropriate accounting agent."""
        agent_id = self.route(intent_keywords or [])
        agent = self._registry.get(agent_id)
        if agent is None:
            logger.warning("AccountingCenter: no agent found for id=%s", agent_id)
            agent = self._registry.get("finance_ops_chief")
        if agent is None:
            raise RuntimeError("AccountingCenter: no agent available")
        logger.info("AccountingCenter routing to agent=%s (requires_review=True)", agent_id)
        return await agent.run(task, ctx)

    def list_domains(self) -> list[str]:
        return sorted(set(self.DOMAIN_MAP.values()))
