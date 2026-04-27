"""BehavioralLab — behavioral pattern analysis, habit science, cognitive models."""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class BehavioralLab(LabsFramework):
    lab_id = "behavioral"
    lab_name = "Behavioral Lab"
    description = "Behavioral pattern analysis, habit science, cognitive biases, and decision heuristics."
    agents = ["habit_engineer", "mood_pattern", "impulse_filter", "pattern_detector", "bias_detector"]
    tools = ["memory_tool", "code_exec"]
    dataset_description = "Habit logs, mood journals, impulse records, decision history, behavioral patterns."
    benchmarks = {"pattern_detection_precision": 0.80, "intervention_success_rate": 0.65}
    output_standards = {"behavioral_report": "Weekly pattern analysis with actionable interventions"}
    requires_human_review = False
    model = "claude-sonnet-4-6"
    experiment_templates = [
        {
            "name": "Habit Loop Detection — Cue-Routine-Reward Mapping",
            "description": "Identify dominant habit loops from daily activity logs and measure intervention success.",
            "hypothesis": {
                "statement": "AI-detected habit cues match self-reported patterns ≥80% of the time",
                "metric": "pattern_detection_precision",
                "success_threshold": 0.80,
                "baseline": 0.55,
            },
            "control_config": {"detection": "self_reported"},
            "treatment_config": {"detection": "ai_log_analysis", "window_days": 14},
            "tags": ["behavioral", "habits", "detection"],
        },
        {
            "name": "Cognitive Bias Nudge — Pre-Decision Framing",
            "description": "Test whether presenting a bias warning before decisions reduces loss-aversion and anchoring effects.",
            "hypothesis": {
                "statement": "Bias framing nudges improve decision quality score by ≥15%",
                "metric": "intervention_success_rate",
                "success_threshold": 0.65,
                "baseline": 0.50,
            },
            "control_config": {"nudge": False},
            "treatment_config": {"nudge": True, "bias_types": ["anchoring", "loss_aversion", "confirmation"]},
            "tags": ["behavioral", "bias", "nudge"],
        },
        {
            "name": "Impulse Filter Effectiveness — Delay Intervention",
            "description": "Measure whether a 10-minute delay prompt reduces impulsive decisions flagged by the impulse filter.",
            "hypothesis": {
                "statement": "10-minute delay prompts reduce impulsive action rate by ≥25%",
                "metric": "intervention_success_rate",
                "success_threshold": 0.65,
                "baseline": 0.40,
            },
            "control_config": {"delay_minutes": 0},
            "treatment_config": {"delay_minutes": 10, "reflection_prompt": True},
            "tags": ["behavioral", "impulse", "intervention"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/behavioral_experiments.json") -> None:
        super().__init__(data_path=data_path)

    def describe(self) -> dict:
        return {"lab_id": self.lab_id, "lab_name": self.lab_name, "agents": self.agents,
                "tools": self.tools, "requires_human_review": self.requires_human_review, "model": self.model}

lab = BehavioralLab()
