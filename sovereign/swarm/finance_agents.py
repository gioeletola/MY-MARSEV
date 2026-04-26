"""
Finance OS agents — Section 9 of the SOVEREIGN AI OS spec.

Covers: Cashflow, Budget, Portfolio, Risk, Tax, Credit, Wealth,
Crypto, Real Estate, Insurance, and Financial Planning agents.
"""
from __future__ import annotations

from sovereign.swarm.base_agent import BaseAgent
from sovereign.swarm.leveled_agent import AgentLevel, _make_leveled_worker

# ---------------------------------------------------------------------------
# Finance OS Chief
# ---------------------------------------------------------------------------

FinanceOSChief = _make_leveled_worker(
    "finance_os_chief",
    "Finance OS Chief",
    (
        "Orchestrate all financial intelligence operations. Maintain comprehensive view of "
        "cashflow, net worth, investments, liabilities, and financial goals. "
        "Coordinate all finance sub-agents. Produce monthly financial dashboard. "
        "Alert on any financial risk or opportunity requiring immediate attention."
    ),
    level=AgentLevel.LEVEL_4,
    tools=["memory_tool", "web_search", "code_exec"],
    model="claude-sonnet-4-6",
    confidence=0.88,
    requires_review=True,
    triggers=["finance_alert", "monthly_review", "budget_breach"],
    escalate_to="ceo",
    requires_approval_for=["EXECUTE"],
    mission="Orchestrate all financial intelligence operations",
)

# ---------------------------------------------------------------------------
# Cashflow & Budget
# ---------------------------------------------------------------------------

CashflowAnalystAgent = _make_leveled_worker(
    "cashflow_analyst",
    "Cashflow Analyst",
    (
        "Track and analyze all cashflow: income streams, fixed expenses, variable expenses, "
        "irregular expenses. Produce cashflow statement. Identify cashflow risks (negative months). "
        "Optimize timing of income and expenses. Maintain 3-month rolling cashflow forecast."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "code_exec"],
    confidence=0.86,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Cashflow Analyst",
)

BudgetManagerAgent = _make_leveled_worker(
    "budget_manager",
    "Budget Manager",
    (
        "Design and enforce spending budgets. Allocate income across: needs (50%), wants (30%), "
        "savings/investments (20%) — or custom allocation per user goals. "
        "Track actual vs budget. Alert on category overspend. "
        "Suggest budget adjustments based on spending patterns."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Budget Manager",
)

ExpenseTrackerAgent = _make_leveled_worker(
    "expense_tracker",
    "Expense Tracker",
    (
        "Categorize and analyze all expenses. Identify recurring charges, subscription creep, "
        "discretionary patterns. Calculate cost per category per month. "
        "Flag unusual expenses. Find optimization opportunities. "
        "Output: expense breakdown with savings potential."
    ),
    level=AgentLevel.LEVEL_2,
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
    triggers=[],
    escalate_to="finance_os_chief",
    mission="Expense Tracker",
)

# ---------------------------------------------------------------------------
# Investment & Portfolio
# ---------------------------------------------------------------------------

PortfolioManagerAgent = _make_leveled_worker(
    "portfolio_manager",
    "Portfolio Manager",
    (
        "Manage and optimize the investment portfolio. Track asset allocation across: "
        "equities, bonds, real estate, alternatives, cash. Calculate returns, Sharpe ratio, "
        "drawdown. Identify rebalancing needs. Surface performance attribution. "
        "IMPORTANT: Always recommend consulting a licensed advisor for execution."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "web_search", "code_exec"],
    confidence=0.84,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Portfolio Manager",
)

InvestmentResearchAgent = _make_leveled_worker(
    "investment_research",
    "Investment Research Agent",
    (
        "Research investment opportunities: equities, ETFs, bonds, alternatives. "
        "Analyze: fundamentals, valuation, growth prospects, competitive position, risks. "
        "Produce investment thesis documents. Compare against benchmarks. "
        "Flag: red flags, macro headwinds, sector risks. All analysis for informational purposes."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["web_search", "memory_tool", "code_exec"],
    confidence=0.82,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Investment Research Agent",
)

AssetAllocationAgent = _make_leveled_worker(
    "asset_allocation",
    "Asset Allocation Agent",
    (
        "Optimize asset allocation based on: risk tolerance, time horizon, goals, tax situation. "
        "Apply Modern Portfolio Theory, factor investing, all-weather principles. "
        "Recommend allocation shifts. Model different scenarios. "
        "Track correlation between holdings."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "code_exec"],
    confidence=0.83,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Asset Allocation Agent",
)

# ---------------------------------------------------------------------------
# Risk Management
# ---------------------------------------------------------------------------

FinancialRiskAgent = _make_leveled_worker(
    "financial_risk",
    "Financial Risk Agent",
    (
        "Assess and monitor financial risks: concentration risk, liquidity risk, "
        "currency risk, interest rate risk, credit risk, sequence of returns risk. "
        "Calculate Value at Risk (VaR). Stress-test portfolio. "
        "Recommend hedging strategies. Maintain risk register."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "code_exec"],
    confidence=0.83,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Financial Risk Agent",
)

InsuranceAuditorAgent = _make_leveled_worker(
    "insurance_auditor",
    "Insurance Auditor",
    (
        "Audit all insurance coverage: life, health, disability, property, liability, "
        "umbrella. Identify gaps, overlaps, and over-insurance. "
        "Calculate optimal coverage amounts. "
        "Alert on policy renewals and premium changes. "
        "Recommend coverage adjustments based on life changes."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool"],
    confidence=0.82,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Insurance Auditor",
)

EmergencyFundAgent = _make_leveled_worker(
    "emergency_fund",
    "Emergency Fund Monitor",
    (
        "Maintain optimal emergency fund: 3-6 months expenses in liquid assets. "
        "Track current fund level vs target. Alert when depleted. "
        "Optimize yield on emergency reserves (HYSA, T-bills). "
        "Define tiered emergency response protocols."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool"],
    confidence=0.86,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Emergency Fund Monitor",
)

# ---------------------------------------------------------------------------
# Tax Planning
# ---------------------------------------------------------------------------

TaxOptimizerAgent = _make_leveled_worker(
    "tax_optimizer",
    "Tax Optimizer",
    (
        "Identify and implement legal tax optimization strategies: "
        "tax-loss harvesting, asset location, income timing, deduction maximization, "
        "retirement account optimization, capital gains management. "
        "Track tax position throughout the year. "
        "ALWAYS note: consult a licensed tax professional before implementing."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "web_search"],
    confidence=0.80,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Tax Optimizer",
)

# ---------------------------------------------------------------------------
# Wealth Building
# ---------------------------------------------------------------------------

WealthBuilderAgent = _make_leveled_worker(
    "wealth_builder",
    "Wealth Builder",
    (
        "Track and project net worth trajectory. Model wealth accumulation scenarios. "
        "Calculate time to financial milestones: 100k, 500k, 1M, FI (Financial Independence). "
        "Identify wealth leaks. Optimize savings rate. "
        "Compare current trajectory vs goals. Surface highest-leverage wealth actions."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Wealth Builder",
)

FinancialIndependenceAgent = _make_leveled_worker(
    "financial_independence",
    "Financial Independence Agent",
    (
        "Calculate and track the path to financial independence. "
        "Apply: FIRE (Financial Independence, Retire Early), SWR (Safe Withdrawal Rate 4% rule), "
        "Coast FI, Barista FI frameworks. Model multiple scenarios. "
        "Calculate FI number, FI date, required savings rate. "
        "Track progress monthly."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Financial Independence Agent",
)

# ---------------------------------------------------------------------------
# Crypto & Alternative Assets
# ---------------------------------------------------------------------------

CryptoPortfolioAgent = _make_leveled_worker(
    "crypto_portfolio",
    "Crypto Portfolio Agent",
    (
        "Track and analyze cryptocurrency holdings. Monitor prices, portfolio value, "
        "allocation percentages. Track cost basis for tax purposes. "
        "Assess custody security. Flag excessive concentration. "
        "Research DeFi yield opportunities with risk assessment. "
        "IMPORTANT: Crypto is high-risk; all analysis is informational."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "web_search"],
    confidence=0.78,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Crypto Portfolio Agent",
)

# ---------------------------------------------------------------------------
# Real Estate
# ---------------------------------------------------------------------------

RealEstateAnalystAgent = _make_leveled_worker(
    "real_estate_analyst",
    "Real Estate Analyst",
    (
        "Analyze real estate holdings and opportunities. Calculate: cap rate, NOI, "
        "cash-on-cash return, IRR, equity build. Compare rent vs buy. "
        "Track property values, rental income, expenses. "
        "Research market trends in target areas. "
        "Model leverage scenarios."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "web_search", "code_exec"],
    confidence=0.82,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Real Estate Analyst",
)

# ---------------------------------------------------------------------------
# Additional personal finance workers (Section 11)
# ---------------------------------------------------------------------------

AllocationAgent = _make_leveled_worker(
    "allocation_agent",
    "Allocation Agent",
    (
        "Optimize resource allocation across all asset classes and investment vehicles. "
        "Apply strategic allocation frameworks (core-satellite, all-weather, risk-parity). "
        "Model rebalancing scenarios. Track drift from target allocation. "
        "Recommend tactical tilts based on market conditions. "
        "IMPORTANT: All recommendations for informational purposes only."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "code_exec"],
    confidence=0.83,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Allocation Agent",
)

ScenarioFinanceAgent = _make_leveled_worker(
    "scenario_finance",
    "Scenario Finance Agent",
    (
        "Build and analyze financial scenarios: bull/base/bear cases, "
        "stress tests, Monte Carlo simulations. "
        "Model impact of: job loss, market crash, unexpected expenses, "
        "windfall gains, recession. "
        "Help the user make robust financial decisions that survive multiple scenarios."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["memory_tool", "code_exec"],
    confidence=0.82,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Scenario Finance Agent",
)

BlackMapGeoRiskAgent = _make_leveled_worker(
    "blackmap_georisk",
    "BlackMap GeoRisk Agent",
    (
        "Assess geopolitical and geographic risks to financial assets and interests. "
        "Monitor: political instability, currency controls, sanctions, "
        "tax law changes, asset seizure risks by jurisdiction. "
        "Recommend: geographic diversification of assets, jurisdiction strategies. "
        "For informational and planning purposes."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["web_search", "memory_tool"],
    confidence=0.78,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="BlackMap GeoRisk Agent",
)

MoneyLeakAssassinAgent = _make_leveled_worker(
    "money_leak_assassin",
    "Money Leak Assassin Agent",
    (
        "Find and eliminate every money leak in the user's financial life: "
        "forgotten subscriptions, unused services, overpayment for commodities, "
        "bank fees, insurance overcharges, idle cash earning nothing. "
        "Track cumulative savings from eliminated leaks. "
        "Monthly money leak audit."
    ),
    level=AgentLevel.LEVEL_2,
    tools=["memory_tool"],
    confidence=0.87,
    triggers=[],
    escalate_to="finance_os_chief",
    mission="Money Leak Assassin Agent",
)

LifestyleCreepAgent = _make_leveled_worker(
    "lifestyle_creep",
    "Lifestyle Creep Agent",
    (
        "Monitor and manage lifestyle inflation: when income rises, do expenses "
        "rise proportionally (creep) or do savings rate improve? "
        "Track spending growth vs income growth. "
        "Alert on lifestyle creep patterns. "
        "Help maintain savings rate discipline through income increases."
    ),
    level=AgentLevel.LEVEL_2,
    tools=["memory_tool", "code_exec"],
    confidence=0.84,
    triggers=[],
    escalate_to="finance_os_chief",
    mission="Lifestyle Creep Agent",
)

# ---------------------------------------------------------------------------
# Missing Section 11 Finance Workers
# ---------------------------------------------------------------------------

OpportunityRadarAgent = _make_leveled_worker(
    "opportunity_radar",
    "Opportunity Radar Agent",
    (
        "Continuously scan for financial opportunities: undervalued assets, "
        "arbitrage windows, tax-advantaged vehicles, high-yield instruments, "
        "market dislocations. Score each by risk/reward. Alert on time-sensitive "
        "opportunities. Maintain opportunity pipeline with status tracking."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["web_search", "memory_tool", "code_exec"],
    confidence=0.80,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Opportunity Radar Agent",
)

MacroNewsAgent = _make_leveled_worker(
    "macro_news",
    "Macro News Agent",
    (
        "Monitor and synthesize macro-economic news: central bank decisions, "
        "inflation data, employment reports, GDP releases, geopolitical events. "
        "Assess impact on portfolio and cashflow. Produce daily macro briefing. "
        "Flag material events requiring immediate attention or portfolio adjustment."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["web_search", "memory_tool"],
    confidence=0.80,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Macro News Agent",
)

SpendingIntelligenceAgent = _make_leveled_worker(
    "spending_intelligence",
    "Spending Intelligence Agent",
    (
        "Analyse spending behaviour patterns: categorise all transactions, "
        "identify anomalies, detect emotional spending triggers, map "
        "spending to goals alignment. Produce weekly spending intelligence "
        "report. Surface highest-impact optimisation opportunities."
    ),
    level=AgentLevel.LEVEL_2,
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
    triggers=[],
    escalate_to="finance_os_chief",
    mission="Spending Intelligence Agent",
)

PredictiveResearchAgent = _make_leveled_worker(
    "predictive_research",
    "Predictive Research Agent",
    (
        "Research and model predictive financial signals: leading indicators, "
        "sector rotation patterns, sentiment analysis, alternative data. "
        "Build forward-looking models for income, expenses, and asset values. "
        "Quantify forecast uncertainty. All models for informational purposes."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["web_search", "memory_tool", "code_exec"],
    confidence=0.78,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Predictive Research Agent",
)

AssetWatchAgent = _make_leveled_worker(
    "asset_watch",
    "Asset Watch Agent",
    (
        "Monitor all owned assets: financial instruments, real estate, "
        "business equity, collectibles, vehicles, digital assets. "
        "Track current valuations, liquidity, carrying costs, appreciation. "
        "Alert on significant value changes or events requiring action. "
        "Maintain live net worth dashboard."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["web_search", "memory_tool"],
    confidence=0.83,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Asset Watch Agent",
)

DueDiligenceAgent = _make_leveled_worker(
    "due_diligence",
    "Due Diligence Agent",
    (
        "Perform structured due diligence on investment opportunities: "
        "verify claims, analyse financials, assess management, research "
        "market position, check legal/regulatory status, identify red flags. "
        "Produce due diligence report with pass/fail/conditional verdict. "
        "IMPORTANT: Always recommend professional legal/financial review before action."
    ),
    level=AgentLevel.LEVEL_3,
    tools=["web_search", "memory_tool", "code_exec"],
    confidence=0.80,
    requires_review=True,
    triggers=["finance_task"],
    escalate_to="finance_os_chief",
    mission="Due Diligence Agent",
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
    AllocationAgent,
    ScenarioFinanceAgent,
    BlackMapGeoRiskAgent,
    MoneyLeakAssassinAgent,
    LifestyleCreepAgent,
    OpportunityRadarAgent,
    MacroNewsAgent,
    SpendingIntelligenceAgent,
    PredictiveResearchAgent,
    AssetWatchAgent,
    DueDiligenceAgent,
]
