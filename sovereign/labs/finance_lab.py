"""
FinanceLab — financial modeling, predictive research, portfolio optimization.
"""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class FinanceLab(LabsFramework):
    """Experimental sandbox for financial modeling and portfolio optimization."""

    lab_id: str = "finance"
    lab_name: str = "Finance Lab"
    description: str = (
        "Financial modeling, predictive market research, portfolio optimization, "
        "and quantitative asset allocation experiments."
    )

    agents: list[str] = [
        "predictive_research",
        "scenario_finance",
        "asset_allocation",
        "portfolio_manager",
    ]
    tools: list[str] = ["code_exec", "web_search", "memory_tool"]

    dataset_description: str = (
        "Price history, fundamental data, macro indicators, earnings reports, "
        "alternative data feeds, and portfolio performance records."
    )
    benchmarks: dict[str, float] = {
        "model_accuracy": 0.75,
        "sharpe_ratio_improvement": 0.20,
        "drawdown_reduction": 0.15,
        "allocation_efficiency": 0.80,
    }
    output_standards: dict[str, str] = {
        "financial_model": "Spreadsheet-ready model with assumptions and sensitivities",
        "portfolio_report": "Holdings, weights, risk metrics, and rebalancing triggers",
        "market_brief": "Quantitative market summary with actionable signals",
        "allocation_plan": "Asset allocation with rationale and rebalancing schedule",
    }
    requires_human_review: bool = False
    model: str = "claude-sonnet-4-6"
    experiment_templates = [
        {
            "name": "Portfolio Optimisation — Sharpe Ratio Maximisation",
            "description": "Test whether rebalancing allocation using rolling-window Sharpe maximisation improves risk-adjusted returns vs static 60/40.",
            "hypothesis": {"statement": "Dynamic rebalancing based on 90-day rolling Sharpe ratios will outperform static 60/40", "metric": "sharpe_ratio_improvement", "success_threshold": 0.20, "baseline": 0.0},
            "control_config": {"allocation": "60/40", "rebalance": "annual"},
            "treatment_config": {"allocation": "dynamic", "window_days": 90, "rebalance": "monthly"},
            "tags": ["finance", "portfolio", "sharpe"],
        },
        {
            "name": "Cashflow Forecast Accuracy — ML vs Rule-based",
            "description": "Compare 30-day cashflow forecast accuracy between rule-based projection and ML regression model.",
            "hypothesis": {"statement": "ML regression model achieves ≥15% lower MAPE than rule-based forecast", "metric": "model_accuracy", "success_threshold": 0.75, "baseline": 0.60},
            "control_config": {"model": "rule_based"},
            "treatment_config": {"model": "ml_regression", "features": ["seasonality", "trend", "anomalies"]},
            "tags": ["finance", "cashflow", "forecasting"],
        },
        {
            "name": "Tax Optimisation — Tax-Loss Harvesting Impact",
            "description": "Measure tax savings from systematic tax-loss harvesting on a diversified portfolio.",
            "hypothesis": {"statement": "Tax-loss harvesting reduces annual tax liability by ≥10%", "metric": "allocation_efficiency", "success_threshold": 0.80, "baseline": 0.65},
            "control_config": {"harvesting": False},
            "treatment_config": {"harvesting": True, "threshold_pct": 5.0},
            "tags": ["finance", "tax", "optimisation"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/finance_experiments.json") -> None:
        super().__init__(data_path=data_path)

    def describe(self) -> dict:
        return {
            "lab_id": self.lab_id,
            "lab_name": self.lab_name,
            "agents": self.agents,
            "tools": self.tools,
            "benchmarks": self.benchmarks,
            "requires_human_review": self.requires_human_review,
            "model": self.model,
        }


lab = FinanceLab()
