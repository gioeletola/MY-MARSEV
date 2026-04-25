"""DecisionScienceLab — decision quality, cognitive bias detection, option analysis."""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class DecisionScienceLab(LabsFramework):
    lab_id = "decision_science"
    lab_name = "Decision Science Lab"
    description = "Decision quality research: cognitive bias detection, option generation, regret minimization."
    agents = ["option_generator", "devils_advocate", "second_opinion", "regret_minimizer",
              "tradeoff_agent", "reversibility_agent", "decision_quality"]
    tools = ["memory_tool", "code_exec"]
    dataset_description = "Decision logs, outcome tracking, bias detection reports, option analyses."
    benchmarks = {"decision_quality_score": 0.80, "bias_detection_rate": 0.75}
    output_standards = {"decision_report": "Structured decision brief with options, risks, and recommendation"}
    requires_human_review = False
    model = "claude-opus-4-6"

    def __init__(self, data_path: str = "data/labs/decision_experiments.json") -> None:
        super().__init__(data_path=data_path)

    def describe(self) -> dict:
        return {"lab_id": self.lab_id, "lab_name": self.lab_name, "agents": self.agents,
                "tools": self.tools, "requires_human_review": self.requires_human_review, "model": self.model}

lab = DecisionScienceLab()
