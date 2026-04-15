"""
Finance OS agents — Section 9 of the SOVEREIGN AI OS spec.

Covers: Cashflow, Budget, Portfolio, Risk, Tax, Credit, Wealth,
Crypto, Real Estate, Insurance, and Financial Planning agents.
"""
from __future__ import annotations

from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent
from sovereign.output.output_contract import OutputStatus, StructuredOutput


def _make_worker(
    agent_id: str,
    specialty: str,
    instructions: str,
    tools: list[str] | None = None,
    model: str = "claude-sonnet-4-6",
    requires_review: bool = False,
    confidence: float = 0.82,
):
    _tools = tools or ["memory_tool"]
    _model = model
    _review = requires_review
    _conf = confidence

    return type(
        f"{agent_id.replace('-', '_').title()}Agent",
        (BaseAgent,),
        {
            "agent_id": agent_id,
            "model": _model,
            "run": _make_run(agent_id, specialty, instructions, _tools, _review, _conf),
        },
    )


def _make_run(agent_id, specialty, instructions, tools, requires_review, confidence):
    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        import logging
        logger = logging.getLogger(__name__)
        try:
            if not task.tools_allowed:
                task.tools_allowed = list(tools)
            prompt = (
                f"You are the {specialty} of the SOVEREIGN AI OS.\n\n"
                f"{instructions}\n\n"
                f"Task:\n{task.objective}\n\n"
                "Provide precise, data-driven financial analysis with clear recommendations.\n"
                "Always flag items requiring human decision or professional advice."
            )
            result, history = await self._call_with_tools(
                [{"role": "user", "content": prompt}], ctx, task, max_tokens=2048
            )
            out = self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=confidence,
                data={"specialty": specialty, "tool_turns": len(history)},
            )
            out.requires_human_review = requires_review
            return out
        except Exception as exc:
            logger.error("FinanceAgent %s failed: %s", agent_id, exc)
            return StructuredOutput.failure(ctx.session_id, agent_id, task.task_id, str(exc))

    return run


# ---------------------------------------------------------------------------
# Finance OS Chief
# ---------------------------------------------------------------------------

FinanceOSChief = _make_worker(
    "finance_os_chief",
    "Finance OS Chief",
    (
        "Orchestrate all financial intelligence operations. Maintain comprehensive view of "
        "cashflow, net worth, investments, liabilities, and financial goals. "
        "Coordinate all finance sub-agents. Produce monthly financial dashboard. "
        "Alert on any financial risk or opportunity requiring immediate attention."
    ),
    tools=["memory_tool", "web_search", "code_exec"],
    model="claude-sonnet-4-6",
    confidence=0.88,
    requires_review=True,
)

# ---------------------------------------------------------------------------
# Cashflow & Budget
# ---------------------------------------------------------------------------

CashflowAnalystAgent = _make_worker(
    "cashflow_analyst",
    "Cashflow Analyst",
    (
        "Track and analyze all cashflow: income streams, fixed expenses, variable expenses, "
        "irregular expenses. Produce cashflow statement. Identify cashflow risks (negative months). "
        "Optimize timing of income and expenses. Maintain 3-month rolling cashflow forecast."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.86,
    requires_review=True,
)

BudgetManagerAgent = _make_worker(
    "budget_manager",
    "Budget Manager",
    (
        "Design and enforce spending budgets. Allocate income across: needs (50%), wants (30%), "
        "savings/investments (20%) — or custom allocation per user goals. "
        "Track actual vs budget. Alert on category overspend. "
        "Suggest budget adjustments based on spending patterns."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
    requires_review=True,
)

ExpenseTrackerAgent = _make_worker(
    "expense_tracker",
    "Expense Tracker",
    (
        "Categorize and analyze all expenses. Identify recurring charges, subscription creep, "
        "discretionary patterns. Calculate cost per category per month. "
        "Flag unusual expenses. Find optimization opportunities. "
        "Output: expense breakdown with savings potential."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
)

# ---------------------------------------------------------------------------
# Investment & Portfolio
# ---------------------------------------------------------------------------

PortfolioManagerAgent = _make_worker(
    "portfolio_manager",
    "Portfolio Manager",
    (
        "Manage and optimize the investment portfolio. Track asset allocation across: "
        "equities, bonds, real estate, alternatives, cash. Calculate returns, Sharpe ratio, "
        "drawdown. Identify rebalancing needs. Surface performance attribution. "
        "IMPORTANT: Always recommend consulting a licensed advisor for execution."
    ),
    tools=["memory_tool", "web_search", "code_exec"],
    confidence=0.84,
    requires_review=True,
)

InvestmentResearchAgent = _make_worker(
    "investment_research",
    "Investment Research Agent",
    (
        "Research investment opportunities: equities, ETFs, bonds, alternatives. "
        "Analyze: fundamentals, valuation, growth prospects, competitive position, risks. "
        "Produce investment thesis documents. Compare against benchmarks. "
        "Flag: red flags, macro headwinds, sector risks. All analysis for informational purposes."
    ),
    tools=["web_search", "memory_tool", "code_exec"],
    confidence=0.82,
    requires_review=True,
)

AssetAllocationAgent = _make_worker(
    "asset_allocation",
    "Asset Allocation Agent",
    (
        "Optimize asset allocation based on: risk tolerance, time horizon, goals, tax situation. "
        "Apply Modern Portfolio Theory, factor investing, all-weather principles. "
        "Recommend allocation shifts. Model different scenarios. "
        "Track correlation between holdings."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.83,
    requires_review=True,
)

# ---------------------------------------------------------------------------
# Risk Management
# ---------------------------------------------------------------------------

FinancialRiskAgent = _make_worker(
    "financial_risk",
    "Financial Risk Agent",
    (
        "Assess and monitor financial risks: concentration risk, liquidity risk, "
        "currency risk, interest rate risk, credit risk, sequence of returns risk. "
        "Calculate Value at Risk (VaR). Stress-test portfolio. "
        "Recommend hedging strategies. Maintain risk register."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.83,
    requires_review=True,
)

InsuranceAuditorAgent = _make_worker(
    "insurance_auditor",
    "Insurance Auditor",
    (
        "Audit all insurance coverage: life, health, disability, property, liability, "
        "umbrella. Identify gaps, overlaps, and over-insurance. "
        "Calculate optimal coverage amounts. "
        "Alert on policy renewals and premium changes. "
        "Recommend coverage adjustments based on life changes."
    ),
    tools=["memory_tool"],
    confidence=0.82,
    requires_review=True,
)

EmergencyFundAgent = _make_worker(
    "emergency_fund",
    "Emergency Fund Monitor",
    (
        "Maintain optimal emergency fund: 3-6 months expenses in liquid assets. "
        "Track current fund level vs target. Alert when depleted. "
        "Optimize yield on emergency reserves (HYSA, T-bills). "
        "Define tiered emergency response protocols."
    ),
    tools=["memory_tool"],
    confidence=0.86,
)

# ---------------------------------------------------------------------------
# Tax Planning
# ---------------------------------------------------------------------------

TaxOptimizerAgent = _make_worker(
    "tax_optimizer",
    "Tax Optimizer",
    (
        "Identify and implement legal tax optimization strategies: "
        "tax-loss harvesting, asset location, income timing, deduction maximization, "
        "retirement account optimization, capital gains management. "
        "Track tax position throughout the year. "
        "ALWAYS note: consult a licensed tax professional before implementing."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.80,
    requires_review=True,
)

# ---------------------------------------------------------------------------
# Wealth Building
# ---------------------------------------------------------------------------

WealthBuilderAgent = _make_worker(
    "wealth_builder",
    "Wealth Builder",
    (
        "Track and project net worth trajectory. Model wealth accumulation scenarios. "
        "Calculate time to financial milestones: 100k, 500k, 1M, FI (Financial Independence). "
        "Identify wealth leaks. Optimize savings rate. "
        "Compare current trajectory vs goals. Surface highest-leverage wealth actions."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
)

FinancialIndependenceAgent = _make_worker(
    "financial_independence",
    "Financial Independence Agent",
    (
        "Calculate and track the path to financial independence. "
        "Apply: FIRE (Financial Independence, Retire Early), SWR (Safe Withdrawal Rate 4% rule), "
        "Coast FI, Barista FI frameworks. Model multiple scenarios. "
        "Calculate FI number, FI date, required savings rate. "
        "Track progress monthly."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
)

# ---------------------------------------------------------------------------
# Crypto & Alternative Assets
# ---------------------------------------------------------------------------

CryptoPortfolioAgent = _make_worker(
    "crypto_portfolio",
    "Crypto Portfolio Agent",
    (
        "Track and analyze cryptocurrency holdings. Monitor prices, portfolio value, "
        "allocation percentages. Track cost basis for tax purposes. "
        "Assess custody security. Flag excessive concentration. "
        "Research DeFi yield opportunities with risk assessment. "
        "IMPORTANT: Crypto is high-risk; all analysis is informational."
    ),
    tools=["memory_tool", "web_search"],
    confidence=0.78,
    requires_review=True,
)

# ---------------------------------------------------------------------------
# Real Estate
# ---------------------------------------------------------------------------

RealEstateAnalystAgent = _make_worker(
    "real_estate_analyst",
    "Real Estate Analyst",
    (
        "Analyze real estate holdings and opportunities. Calculate: cap rate, NOI, "
        "cash-on-cash return, IRR, equity build. Compare rent vs buy. "
        "Track property values, rental income, expenses. "
        "Research market trends in target areas. "
        "Model leverage scenarios."
    ),
    tools=["memory_tool", "web_search", "code_exec"],
    confidence=0.82,
    requires_review=True,
)

# ---------------------------------------------------------------------------
# Export registry
# ---------------------------------------------------------------------------

FINANCE_AGENTS: list[type[BaseAgent]] = [
    FinanceOSChief,
    CashflowAnalystAgent,
    BudgetManagerAgent,
    ExpenseTrackerAgent,
    PortfolioManagerAgent,
    InvestmentResearchAgent,
    AssetAllocationAgent,
    FinancialRiskAgent,
    InsuranceAuditorAgent,
    EmergencyFundAgent,
    TaxOptimizerAgent,
    WealthBuilderAgent,
    FinancialIndependenceAgent,
    CryptoPortfolioAgent,
    RealEstateAnalystAgent,
]
