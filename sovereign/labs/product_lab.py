"""
ProductLab — product ideation, feature design, user research.
"""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class ProductLab(LabsFramework):
    """Experimental sandbox for product ideation, feature design, and user research."""

    lab_id: str = "product"
    lab_name: str = "Product Lab"
    description: str = (
        "Product ideation, feature design experiments, user research synthesis, "
        "and QA testing frameworks for SOVEREIGN OS applications."
    )

    agents: list[str] = [
        "app_builder",
        "qa_testing",
        "toolsmith_agent",
    ]
    tools: list[str] = ["code_exec", "memory_tool"]

    dataset_description: str = (
        "User feedback, feature usage analytics, bug reports, "
        "product roadmap history, and competitive feature benchmarks."
    )
    benchmarks: dict[str, float] = {
        "feature_adoption_rate": 0.60,
        "bug_detection_coverage": 0.90,
        "user_satisfaction_score": 0.80,
        "build_success_rate": 0.95,
    }
    output_standards: dict[str, str] = {
        "product_spec": "Feature brief with user stories, acceptance criteria, and wireframe",
        "qa_test_plan": "Test cases with expected vs actual results and severity ratings",
        "user_research_summary": "Insight clusters, verbatim quotes, and prioritized needs",
        "tool_spec": "API contract, inputs/outputs, error handling, and usage examples",
    }
    requires_human_review: bool = False
    model: str = "claude-sonnet-4-6"
    experiment_templates: list = [
        {
            "name": "Product Lab — Feature Adoption A/B",
            "description": "Test guided onboarding vs self-serve for new feature adoption.",
            "hypothesis": {"statement": "Guided onboarding improves feature adoption rate above 70%",
                           "metric": "feature_adoption_rate", "success_threshold": 0.70, "baseline": 0.40},
            "control_config": {"onboarding": "self_serve"}, "treatment_config": {"onboarding": "guided"},
            "tags": ["product", "onboarding", "adoption"],
        },
        {
            "name": "Product Lab — QA Coverage Benchmark",
            "description": "Automated test suite vs manual QA for bug detection coverage.",
            "hypothesis": {"statement": "Automated suite achieves ≥90% bug detection coverage",
                           "metric": "bug_detection_coverage", "success_threshold": 0.90, "baseline": 0.65},
            "control_config": {"qa": "manual"}, "treatment_config": {"qa": "automated"},
            "tags": ["product", "qa", "testing"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/product_experiments.json") -> None:
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


lab = ProductLab()
