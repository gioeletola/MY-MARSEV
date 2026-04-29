"""Investing superpower pack — valuation, portfolio, macro, frameworks."""
from __future__ import annotations

INVESTING_PACK = {
    "id": "investing",
    "name": "Institutional Investor Mind",
    "version": "1.0",
    "description": "Valuation frameworks, portfolio construction, macro analysis, risk management.",
    "valuation": {
        "DCF": {
            "description": "Discounted Cash Flow — intrinsic value = sum of future free cash flows discounted to present",
            "formula": "PV = FCF1/(1+r) + FCF2/(1+r)² + ... + Terminal/(1+r)ⁿ",
            "inputs": ["Revenue growth rate", "FCF margin", "Discount rate (WACC)", "Terminal growth rate"],
            "pitfall": "Terminal value often accounts for 70-80% of value — garbage in, garbage out",
        },
        "comps": {
            "description": "Comparable company analysis — relative valuation",
            "multiples": {
                "EV/Revenue": "SaaS early stage, high-growth",
                "EV/EBITDA": "Mature businesses, PE acquisitions",
                "P/E": "Profitable companies, earnings-driven",
                "P/FCF": "Better than P/E — harder to manipulate",
                "EV/EBIT": "Operational earnings, capital structure neutral",
            },
        },
        "rule_of_40": "For SaaS: Revenue growth rate + FCF margin ≥ 40% = healthy",
        "LBO": "Leveraged buyout: buy with debt, improve operations, sell higher — PE standard",
    },
    "portfolio_construction": {
        "core_satellite": {
            "core": "60-70%: low-cost index funds (S&P500, World)",
            "satellite": "20-30%: active bets in conviction areas",
            "speculative": "5-10%: high-risk/high-reward (crypto, early stage)",
        },
        "kelly_criterion": {
            "formula": "f* = (bp - q) / b  where b=odds, p=win prob, q=loss prob",
            "practical_rule": "Use half-Kelly to avoid volatility drag: bet ½ of Kelly fraction",
        },
        "correlation_matrix": "True diversification = assets with correlation < 0.3",
        "rebalancing": "Annual rebalancing adds ~0.5% CAGR through enforced buy-low sell-high",
    },
    "macro_signals": {
        "yield_curve": {
            "normal": "Long yields > short yields → growth expected",
            "inverted": "Short yields > long yields → recession signal (18-24 month lead time)",
        },
        "leading_indicators": [
            "ISM Manufacturing PMI (>50 = expansion)",
            "Initial jobless claims",
            "Building permits",
            "Yield curve shape",
            "Consumer confidence",
            "Money supply M2",
        ],
        "fed_watch": "Rate hike cycles compress P/E multiples; rate cuts expand them",
        "dollar_strength": "Strong USD = headwind for US multinationals and commodities",
    },
    "risk_management": {
        "position_sizing": "Never more than 5% in a single name; 2% in speculative bets",
        "stop_loss": "Pre-define exit before entering position — removes emotional decision-making",
        "max_drawdown": "Know your max acceptable drawdown before constructing the portfolio",
        "black_swan_prep": "5% in uncorrelated assets (gold, tail risk hedge, TIPS)",
        "anti_fragility": "Invest in things that benefit from volatility, not just survive it",
    },
    "mental_models": {
        "circle_of_competence": "Only invest in what you understand deeply",
        "margin_of_safety": "Buy significantly below intrinsic value to absorb errors",
        "moat_durability": "How defensible is the competitive advantage in 10 years?",
        "quality_vs_price": "Great business at fair price beats fair business at great price",
        "patience": "Time in market > timing the market for compounding to work",
    },
}


def get_pack() -> dict:
    return INVESTING_PACK


def valuation_framework(name: str) -> dict | str | None:
    return INVESTING_PACK["valuation"].get(name)


def macro_signal(name: str) -> dict | str | None:
    return INVESTING_PACK["macro_signals"].get(name)
