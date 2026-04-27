"""
SimulationLab — Monte Carlo, scenario modeling, stress tests.
"""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class SimulationLab(LabsFramework):
    """Experimental sandbox for Monte Carlo simulations and scenario stress testing."""

    lab_id: str = "simulation"
    lab_name: str = "Simulation Lab"
    description: str = (
        "Monte Carlo simulations, probabilistic scenario modeling, portfolio stress tests, "
        "and quantitative risk analysis across financial and operational domains."
    )

    agents: list[str] = [
        "scenario_simulator",
        "scenario_finance",
        "financial_risk",
    ]
    tools: list[str] = ["code_exec", "memory_tool"]

    dataset_description: str = (
        "Historical market data, economic indicators, volatility surfaces, "
        "correlation matrices, and scenario parameter libraries."
    )
    benchmarks: dict[str, float] = {
        "simulation_accuracy": 0.90,
        "scenario_coverage": 0.85,
        "stress_test_depth": 0.80,
        "convergence_rate": 0.95,
    }
    output_standards: dict[str, str] = {
        "monte_carlo_report": "Distribution plots, percentile tables, and VaR summary",
        "stress_test_results": "Scenario matrix with P&L impact per variable",
        "scenario_narrative": "Plain-language interpretation of simulation outcomes",
        "risk_surface": "Heat map of risk exposure across parameter space",
    }
    requires_human_review: bool = False
    model: str = "claude-sonnet-4-6"
    experiment_templates: list = [
        {
            "name": "Simulation Lab — Monte Carlo Portfolio Stress Test",
            "description": "Run 10,000 Monte Carlo scenarios to assess portfolio VaR.",
            "hypothesis": {"statement": "Portfolio stress test achieves ≥90% simulation accuracy",
                           "metric": "simulation_accuracy", "success_threshold": 0.90, "baseline": 0.70},
            "control_config": {"simulations": 1000}, "treatment_config": {"simulations": 10000},
            "tags": ["simulation", "monte_carlo", "portfolio"],
        },
        {
            "name": "Simulation Lab — Black Swan Scenario Coverage",
            "description": "Test whether tail-risk scenarios are represented in scenario library.",
            "hypothesis": {"statement": "Extended library achieves ≥85% scenario coverage",
                           "metric": "scenario_coverage", "success_threshold": 0.85, "baseline": 0.55},
            "control_config": {"library": "standard"}, "treatment_config": {"library": "extended_tail_risk"},
            "tags": ["simulation", "black_swan", "risk"],
        },
        {
            "name": "Simulation Lab — Convergence Speed Optimisation",
            "description": "Latin hypercube sampling vs random sampling for faster convergence.",
            "hypothesis": {"statement": "Latin hypercube achieves ≥95% convergence rate at half the iterations",
                           "metric": "convergence_rate", "success_threshold": 0.95, "baseline": 0.75},
            "control_config": {"sampling": "random"}, "treatment_config": {"sampling": "latin_hypercube"},
            "tags": ["simulation", "sampling", "optimisation"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/simulation_experiments.json") -> None:
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


lab = SimulationLab()
