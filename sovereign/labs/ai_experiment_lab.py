"""AIExperimentLab — prompt experiments, agent behavior testing, model comparison."""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class AIExperimentLab(LabsFramework):
    lab_id = "ai_experiment"
    lab_name = "AI Experiment Lab"
    description = "Prompt engineering experiments, agent behavior testing, and model comparison studies."
    agents = ["eval_agent", "trust_scoring_agent", "qa_testing"]
    tools = ["code_exec", "memory_tool"]
    dataset_description = "Prompt variants, eval scores, token usage, latency benchmarks, model outputs."
    benchmarks = {"eval_pass_rate": 0.80, "prompt_efficiency": 0.75, "cache_hit_rate": 0.60}
    output_standards = {"experiment_report": "Markdown with hypothesis, results, and recommendation"}
    requires_human_review = False
    model = "claude-opus-4-7"
    experiment_templates = [
        {
            "name": "AI Lab — Prompt Compression A/B",
            "description": "Test compressed vs verbose prompts for efficiency with same output quality.",
            "hypothesis": {"statement": "Compressed prompts achieve ≥80% quality at 40% fewer tokens",
                           "metric": "prompt_efficiency", "success_threshold": 0.80, "baseline": 0.55},
            "control_config": {"prompt_style": "verbose"}, "treatment_config": {"prompt_style": "compressed"},
            "tags": ["ai", "prompt_engineering"],
        },
        {
            "name": "AI Lab — Cache Hit Rate Optimisation",
            "description": "Optimise prompt structure to maximise cache hit rate.",
            "hypothesis": {"statement": "Static prefix reordering increases cache hit rate above 70%",
                           "metric": "cache_hit_rate", "success_threshold": 0.70, "baseline": 0.40},
            "control_config": {"prefix": "dynamic"}, "treatment_config": {"prefix": "static_first"},
            "tags": ["ai", "caching"],
        },
        {
            "name": "AI Lab — Model Routing Accuracy",
            "description": "Evaluate automated model routing (Opus/Sonnet/Haiku) vs manual assignment.",
            "hypothesis": {"statement": "Automated routing achieves ≥80% eval pass rate",
                           "metric": "eval_pass_rate", "success_threshold": 0.80, "baseline": 0.65},
            "control_config": {"routing": "manual"}, "treatment_config": {"routing": "automated"},
            "tags": ["ai", "routing"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/ai_experiments.json") -> None:
        super().__init__(data_path=data_path)

    def describe(self) -> dict:
        return {"lab_id": self.lab_id, "lab_name": self.lab_name, "agents": self.agents,
                "tools": self.tools, "requires_human_review": self.requires_human_review, "model": self.model}

lab = AIExperimentLab()
