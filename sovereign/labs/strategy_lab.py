"""
StrategyLab — market strategy, competitive positioning, growth scenarios.
"""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class StrategyLab(LabsFramework):
    """Experimental sandbox for market strategy and competitive positioning."""

    lab_id: str = "strategy"
    lab_name: str = "Strategy Lab"
    description: str = (
        "Hypothesis-driven research on market strategy, competitive positioning, "
        "growth scenarios, and risk-adjusted decision making."
    )

    agents: list[str] = [
        "scenario_simulator",
        "risk_officer",
        "kpi_architect",
        "decision_support",
    ]
    tools: list[str] = ["web_search", "memory_tool", "code_exec"]

    dataset_description: str = (
        "Market data, competitor intelligence, historical strategy outcomes, "
        "KPI benchmarks, and growth trajectory datasets."
    )
    benchmarks: dict[str, float] = {
        "scenario_coverage": 0.90,
        "risk_identification_rate": 0.85,
        "kpi_alignment_score": 0.80,
        "decision_quality_score": 0.75,
    }
    output_standards: dict[str, str] = {
        "scenario_report": "Structured markdown with risk/reward matrix",
        "kpi_dashboard": "Quantified KPIs with thresholds and owners",
        "strategy_brief": "Executive summary under 500 words with action items",
        "risk_register": "Ranked risks with mitigations and probabilities",
    }
    requires_human_review: bool = False
    model: str = "claude-sonnet-4-6"
    experiment_templates = [
        {
            "name": "Blue Ocean Opportunity Scan",
            "description": "Identify uncontested market spaces by mapping competitor feature clusters and finding whitespace.",
            "hypothesis": {"statement": "Systematic blue ocean canvas analysis will surface ≥3 viable uncontested market spaces", "metric": "scenario_coverage", "success_threshold": 0.90, "baseline": 0.50},
            "control_config": {"method": "porter_five_forces"},
            "treatment_config": {"method": "blue_ocean_canvas", "dimensions": 12},
            "tags": ["strategy", "market", "blue_ocean"],
        },
        {
            "name": "Scenario Planning — 3-Horizon Model",
            "description": "Build and stress-test 3-horizon growth scenarios against macro risk factors.",
            "hypothesis": {"statement": "3-horizon scenario models reduce strategic surprise rate by ≥25%", "metric": "risk_identification_rate", "success_threshold": 0.85, "baseline": 0.60},
            "control_config": {"horizons": 1, "scenarios": ["base"]},
            "treatment_config": {"horizons": 3, "scenarios": ["bear", "base", "bull"], "risk_factors": 8},
            "tags": ["strategy", "scenarios", "risk"],
        },
        {
            "name": "KPI Alignment Audit",
            "description": "Test whether linking individual KPIs to strategic objectives improves team alignment scores.",
            "hypothesis": {"statement": "OKR-aligned KPIs improve strategic alignment score by ≥20%", "metric": "kpi_alignment_score", "success_threshold": 0.80, "baseline": 0.60},
            "control_config": {"kpi_method": "ad_hoc"},
            "treatment_config": {"kpi_method": "okr_linked", "review_cadence": "weekly"},
            "tags": ["strategy", "kpi", "alignment"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/strategy_experiments.json") -> None:
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


lab = StrategyLab()
