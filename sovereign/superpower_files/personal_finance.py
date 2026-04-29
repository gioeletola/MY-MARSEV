"""Personal finance superpower pack — budgeting, investing, debt, and wealth building."""
from __future__ import annotations

PACK = {
    "id": "personal_finance",
    "title": "Personal Finance Mastery",
    "version": "1.0",
    "sections": {
        "foundations": {
            "financial_order_of_operations": [
                "1. Emergency fund (1 month minimum to start)",
                "2. Employer match on pension/401k (free money)",
                "3. Pay high-interest debt (>7% APR)",
                "4. Build 3–6 month emergency fund",
                "5. Max tax-advantaged accounts (ISA, pension, 401k, IRA)",
                "6. Pay medium-interest debt (4–7%)",
                "7. Invest in taxable accounts",
                "8. Pay low-interest debt (<4%)",
            ],
            "net_worth_formula": "Assets - Liabilities = Net Worth",
            "savings_rate_targets": {
                "minimum": "10% of gross income",
                "good": "20% of gross income",
                "FIRE": "50%+ of gross income",
            },
            "rule_of_thumb_ratios": {
                "housing": "≤ 28% of gross monthly income (PITI)",
                "total_debt": "≤ 36% of gross monthly income",
                "emergency_fund": "3–6 months essential expenses",
                "retirement_multiple": "25× annual expenses at retirement (4% rule)",
            },
        },
        "budgeting": {
            "50_30_20": {
                "needs": "50% — housing, food, transport, utilities, minimum debt payments",
                "wants": "30% — dining, entertainment, subscriptions, lifestyle",
                "savings_debt": "20% — savings, investments, extra debt payments",
            },
            "zero_based": "Every pound/dollar assigned a job; income - all categories = 0",
            "pay_yourself_first": "Automate savings/investments before spending; remove temptation",
            "envelope_method": "Physical or digital envelopes per category; stops overspending",
            "key_metrics": [
                "Monthly cashflow (income - expenses)",
                "Savings rate",
                "Debt-to-income ratio",
                "Net worth trajectory (track monthly)",
            ],
        },
        "debt_strategies": {
            "avalanche": {
                "method": "Pay minimums on all; throw extra at highest APR debt",
                "best_for": "Mathematically optimal; saves most interest",
            },
            "snowball": {
                "method": "Pay minimums on all; throw extra at smallest balance",
                "best_for": "Psychological wins; better for motivation",
            },
            "debt_consolidation": "Combine high-interest debts into single lower-rate loan; check fees",
            "good_vs_bad_debt": {
                "potentially_good": "Mortgage, student loans (career-advancing), business loans (positive ROI)",
                "bad": "Credit cards (high APR), payday loans, car loans on depreciating assets",
            },
            "early_payoff_formula": "Monthly saving = (loan_balance × monthly_rate) / (1 - (1+r)^-n) - current_payment",
        },
        "investing": {
            "time_value_of_money": {
                "future_value": "FV = PV × (1 + r)^n",
                "rule_of_72": "Years to double = 72 / annual_return_percent",
                "rule_of_115": "Years to triple = 115 / annual_return_percent",
            },
            "asset_allocation": {
                "by_age_rule": "Bond% ≈ age (conservative); or 110-age for moderate",
                "three_fund_portfolio": "Total market index + international index + bond index",
                "core_principles": [
                    "Diversification reduces unsystematic risk",
                    "Low cost (expense ratio) beats active management long-term",
                    "Time in market beats timing the market",
                    "Rebalance annually or on drift threshold (±5%)",
                ],
            },
            "tax_advantaged_accounts": {
                "UK": {
                    "ISA": "£20k/yr; tax-free growth and withdrawal; use Stocks & Shares ISA",
                    "SIPP": "Pension; 25% tax relief; can't access until 57",
                    "LISA": "£4k/yr; 25% government bonus; for first home or retirement",
                },
                "US": {
                    "401k": "$23k/yr 2024; traditional (pre-tax) or Roth (post-tax)",
                    "IRA": "$7k/yr; traditional or Roth; backdoor Roth for high earners",
                    "HSA": "$4,150/yr single; triple tax advantage; invest surplus",
                },
            },
            "index_funds_vs_active": {
                "data": "~90% of active funds underperform index over 15 years after fees",
                "key_advantage": "Low expense ratios (0.03–0.20% vs 0.75–1.5% active)",
                "recommendation": "Core of portfolio in low-cost total market index funds",
            },
        },
        "fire_movement": {
            "types": {
                "LeanFIRE": "Frugal retirement; typically < £/$/€25k/yr spending",
                "FIRE": "Standard; 25× annual expenses; 4% withdrawal rate",
                "FatFIRE": "Luxury retirement; typically > £/$/€100k/yr spending",
                "BaristaFIRE": "Semi-retire; part-time work covers healthcare/extras",
                "CoastFIRE": "Stop contributing; existing savings grow to retirement number",
            },
            "calculation": {
                "FIRE_number": "Annual expenses × 25",
                "savings_rate_to_FI_years": {
                    "10%": "~40+ years",
                    "25%": "~32 years",
                    "50%": "~17 years",
                    "75%": "~7 years",
                },
                "safe_withdrawal_rate": "4% historically safe over 30 years (Trinity study)",
            },
        },
        "mental_models": [
            "Pay yourself first — automate savings before lifestyle inflation",
            "Avoid lifestyle inflation: raises → savings rate, not spending",
            "Opportunity cost: spending £5/day on coffee = £150k lost over 30 years at 7%",
            "Sunk cost fallacy: past losses shouldn't drive future financial decisions",
            "Hedonic adaptation: expensive things stop feeling special quickly",
            "Compounding is the 8th wonder of the world — start early",
            "Net worth is a marathon, not a sprint — consistency over perfection",
        ],
    },
}
