"""DesignLab — aesthetic design, visual systems, brand identity."""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class DesignLab(LabsFramework):
    lab_id = "design"
    lab_name = "Design Lab"
    description = "Aesthetic design, visual systems, brand identity, and signature style experimentation."
    agents = ["aesthetic_direction", "style_curator", "empire_aesthetic", "concept_lab", "taste_builder"]
    tools = ["memory_tool", "web_search"]
    dataset_description = "Brand guidelines, aesthetic references, visual systems, style archives."
    benchmarks = {"brand_consistency": 0.90, "aesthetic_coherence": 0.85}
    output_standards = {"design_brief": "Visual direction doc with examples and rationale"}
    requires_human_review = False
    model = "claude-sonnet-4-6"
    experiment_templates = [
        {
            "name": "Brand Consistency Audit — AI vs Human Evaluation",
            "description": "Compare brand consistency scores assigned by AI aesthetic analysis vs human creative directors across 50 assets.",
            "hypothesis": {
                "statement": "AI brand scoring aligns with human creative director ratings ≥90% of the time",
                "metric": "brand_consistency",
                "success_threshold": 0.90,
                "baseline": 0.65,
            },
            "control_config": {"evaluator": "human_creative_director"},
            "treatment_config": {"evaluator": "ai_style_curator", "criteria": ["color", "typography", "tone", "layout"]},
            "tags": ["design", "brand", "consistency"],
        },
        {
            "name": "Visual System Coherence — Systematic Style Guide vs Ad-hoc",
            "description": "Measure aesthetic coherence scores for design output produced with a documented style guide vs ad-hoc design decisions.",
            "hypothesis": {
                "statement": "Style guide-constrained design scores ≥15% higher on aesthetic coherence than ad-hoc",
                "metric": "aesthetic_coherence",
                "success_threshold": 0.85,
                "baseline": 0.65,
            },
            "control_config": {"approach": "ad_hoc"},
            "treatment_config": {"approach": "style_guide", "components": ["color_palette", "typography", "spacing", "imagery"]},
            "tags": ["design", "style_guide", "coherence"],
        },
        {
            "name": "Concept Lab Iteration Speed — AI-Assisted Concepting",
            "description": "Measure time-to-first-viable-concept for AI-assisted ideation vs traditional manual design concepting.",
            "hypothesis": {
                "statement": "AI-assisted concepting reduces time-to-viable-concept by ≥40% without sacrificing quality",
                "metric": "brand_consistency",
                "success_threshold": 0.90,
                "baseline": 0.70,
            },
            "control_config": {"method": "manual_concepting"},
            "treatment_config": {"method": "ai_assisted", "iterations": 5, "feedback_loops": 2},
            "tags": ["design", "concepting", "speed"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/design_experiments.json") -> None:
        super().__init__(data_path=data_path)

    def describe(self) -> dict:
        return {"lab_id": self.lab_id, "lab_name": self.lab_name, "agents": self.agents,
                "tools": self.tools, "requires_human_review": self.requires_human_review, "model": self.model}

lab = DesignLab()
