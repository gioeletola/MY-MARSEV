"""BioLab — health, biometrics, and wellness protocol design (informational only)."""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class BioLab(LabsFramework):
    lab_id = "bio"
    lab_name = "Bio Lab"
    description = "Health, biometrics, sleep, fitness, and nutrition protocol design. Informational only."
    agents = ["sleep_agent", "fitness_planner", "nutrition_organizer", "recovery_agent", "health_tracker"]
    tools = ["memory_tool", "code_exec"]
    dataset_description = "Health metrics, sleep logs, workout data, nutrition data, biometric trends."
    benchmarks = {"protocol_adherence": 0.80, "outcome_correlation": 0.70}
    output_standards = {"health_brief": "Weekly health summary with trend analysis"}
    requires_human_review = True
    model = "claude-sonnet-4-6"
    experiment_templates = [
        {
            "name": "Sleep Protocol Optimisation — Sleep Window Timing",
            "description": "Compare cognitive performance metrics for consistent vs variable sleep window schedules over 4 weeks.",
            "hypothesis": {
                "statement": "Consistent sleep windows improve next-day cognitive performance by ≥15%",
                "metric": "protocol_adherence",
                "success_threshold": 0.80,
                "baseline": 0.55,
            },
            "control_config": {"schedule": "variable"},
            "treatment_config": {"schedule": "fixed", "window_hours": 8, "consistency_check": True},
            "tags": ["bio", "sleep", "performance"],
        },
        {
            "name": "Nutrition Timing — Pre-Workout Macronutrient Impact",
            "description": "Measure workout performance correlation against pre-workout carbohydrate and protein intake timing.",
            "hypothesis": {
                "statement": "Protein + carb meal 90min before training improves performance score by ≥10% vs fasted",
                "metric": "outcome_correlation",
                "success_threshold": 0.70,
                "baseline": 0.50,
            },
            "control_config": {"pre_workout": "fasted"},
            "treatment_config": {"pre_workout": "fed", "macros": {"protein_g": 30, "carbs_g": 60}, "timing_min": 90},
            "tags": ["bio", "nutrition", "performance"],
        },
        {
            "name": "Recovery Protocol — Active vs Passive Rest",
            "description": "Compare muscle recovery rate and next-session readiness score for active recovery vs complete rest days.",
            "hypothesis": {
                "statement": "Active recovery days improve readiness score by ≥10% vs passive rest",
                "metric": "outcome_correlation",
                "success_threshold": 0.70,
                "baseline": 0.55,
            },
            "control_config": {"recovery": "passive"},
            "treatment_config": {"recovery": "active", "activity": "low_intensity_cardio", "duration_min": 30},
            "tags": ["bio", "recovery", "fitness"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/bio_experiments.json") -> None:
        super().__init__(data_path=data_path)

    def describe(self) -> dict:
        return {"lab_id": self.lab_id, "lab_name": self.lab_name, "agents": self.agents,
                "tools": self.tools, "requires_human_review": self.requires_human_review, "model": self.model}

lab = BioLab()
