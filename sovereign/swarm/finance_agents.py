"""
Finance OS agents — Section 9 of the SOVEREIGN AI OS spec.

Covers: Cashflow, Budget, Portfolio, Risk, Tax, Credit, Wealth,
Crypto, Real Estate, Insurance, and Financial Planning agents.
"""
from __future__ import annotations

from sovereign.swarm.base_agent import BaseAgent, _make_worker


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
# Additional personal finance workers (Section 11)
# ---------------------------------------------------------------------------

AllocationAgent = _make_worker(
    "allocation_agent",
    "Allocation Agent",
    (
        "Optimize resource allocation across all asset classes and investment vehicles. "
        "Apply strategic allocation frameworks (core-satellite, all-weather, risk-parity). "
        "Model rebalancing scenarios. Track drift from target allocation. "
        "Recommend tactical tilts based on market conditions. "
        "IMPORTANT: All recommendations for informational purposes only."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.83,
    requires_review=True,
)

ScenarioFinanceAgent = _make_worker(
    "scenario_finance",
    "Scenario Finance Agent",
    (
        "Build and analyze financial scenarios: bull/base/bear cases, "
        "stress tests, Monte Carlo simulations. "
        "Model impact of: job loss, market crash, unexpected expenses, "
        "windfall gains, recession. "
        "Help the user make robust financial decisions that survive multiple scenarios."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.82,
    requires_review=True,
)

BlackMapGeoRiskAgent = _make_worker(
    "blackmap_georisk",
    "BlackMap GeoRisk Agent",
    (
        "Assess geopolitical and geographic risks to financial assets and interests. "
        "Monitor: political instability, currency controls, sanctions, "
        "tax law changes, asset seizure risks by jurisdiction. "
        "Recommend: geographic diversification of assets, jurisdiction strategies. "
        "For informational and planning purposes."
    ),
    tools=["web_search", "memory_tool"],
    confidence=0.78,
    requires_review=True,
)

MoneyLeakAssassinAgent = _make_worker(
    "money_leak_assassin",
    "Money Leak Assassin Agent",
    (
        "Find and eliminate every money leak in the user's financial life: "
        "forgotten subscriptions, unused services, overpayment for commodities, "
        "bank fees, insurance overcharges, idle cash earning nothing. "
        "Track cumulative savings from eliminated leaks. "
        "Monthly money leak audit."
    ),
    tools=["memory_tool"],
    confidence=0.87,
)

LifestyleCreepAgent = _make_worker(
    "lifestyle_creep",
    "Lifestyle Creep Agent",
    (
        "Monitor and manage lifestyle inflation: when income rises, do expenses "
        "rise proportionally (creep) or do savings rate improve? "
        "Track spending growth vs income growth. "
        "Alert on lifestyle creep patterns. "
        "Help maintain savings rate discipline through income increases."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.84,
)

# ---------------------------------------------------------------------------
# Missing Section 11 Finance Workers
# ---------------------------------------------------------------------------

OpportunityRadarAgent = _make_worker(
    "opportunity_radar",
    "Opportunity Radar Agent",
    (
        "Continuously scan for financial opportunities: undervalued assets, "
        "arbitrage windows, tax-advantaged vehicles, high-yield instruments, "
        "market dislocations. Score each by risk/reward. Alert on time-sensitive "
        "opportunities. Maintain opportunity pipeline with status tracking."
    ),
    tools=["web_search", "memory_tool", "code_exec"],
    confidence=0.80,
    requires_review=True,
)

MacroNewsAgent = _make_worker(
    "macro_news",
    "Macro News Agent",
    (
        "Monitor and synthesize macro-economic news: central bank decisions, "
        "inflation data, employment reports, GDP releases, geopolitical events. "
        "Assess impact on portfolio and cashflow. Produce daily macro briefing. "
        "Flag material events requiring immediate attention or portfolio adjustment."
    ),
    tools=["web_search", "memory_tool"],
    confidence=0.80,
    requires_review=True,
)

SpendingIntelligenceAgent = _make_worker(
    "spending_intelligence",
    "Spending Intelligence Agent",
    (
        "Analyse spending behaviour patterns: categorise all transactions, "
        "identify anomalies, detect emotional spending triggers, map "
        "spending to goals alignment. Produce weekly spending intelligence "
        "report. Surface highest-impact optimisation opportunities."
    ),
    tools=["memory_tool", "code_exec"],
    confidence=0.85,
)

PredictiveResearchAgent = _make_worker(
    "predictive_research",
    "Predictive Research Agent",
    (
        "Research and model predictive financial signals: leading indicators, "
        "sector rotation patterns, sentiment analysis, alternative data. "
        "Build forward-looking models for income, expenses, and asset values. "
        "Quantify forecast uncertainty. All models for informational purposes."
    ),
    tools=["web_search", "memory_tool", "code_exec"],
    confidence=0.78,
    requires_review=True,
)

AssetWatchAgent = _make_worker(
    "asset_watch",
    "Asset Watch Agent",
    (
        "Monitor all owned assets: financial instruments, real estate, "
        "business equity, collectibles, vehicles, digital assets. "
        "Track current valuations, liquidity, carrying costs, appreciation. "
        "Alert on significant value changes or events requiring action. "
        "Maintain live net worth dashboard."
    ),
    tools=["web_search", "memory_tool"],
    confidence=0.83,
    requires_review=True,
)

DueDiligenceAgent = _make_worker(
    "due_diligence",
    "Due Diligence Agent",
    (
        "Perform structured due diligence on investment opportunities: "
        "verify claims, analyse financials, assess management, research "
        "market position, check legal/regulatory status, identify red flags. "
        "Produce due diligence report with pass/fail/conditional verdict. "
        "IMPORTANT: Always recommend professional legal/financial review before action."
    ),
    tools=["web_search", "memory_tool", "code_exec"],
    confidence=0.80,
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
