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
