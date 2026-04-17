"""
ResearchLab — deep research, literature review, synthesis, citations.
"""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class ResearchLab(LabsFramework):
    """Experimental sandbox for deep research, literature review, and synthesis."""

    lab_id: str = "research"
    lab_name: str = "Research Lab"
    description: str = (
        "Systematic deep research, literature review, knowledge synthesis, "
        "and citation management across domains."
    )

    agents: list[str] = [
        "personal_archivist",
        "knowledge_organizer",
        "insight_agent",
    ]
    tools: list[str] = ["web_search", "memory_tool"]

    dataset_description: str = (
        "Academic papers, reports, news archives, personal notes, "
        "and curated knowledge bases across research domains."
    )
    benchmarks: dict[str, float] = {
        "source_quality_score": 0.85,
        "synthesis_coherence": 0.80,
        "citation_accuracy": 0.95,
        "insight_novelty_score": 0.70,
    }
    output_standards: dict[str, str] = {
        "literature_review": "Structured review with citations in APA format",
        "synthesis_report": "Key themes, contradictions, and open questions",
        "insight_brief": "Distilled insights with supporting evidence",
        "knowledge_map": "Topic clusters with relationship annotations",
    }
    requires_human_review: bool = False
    model: str = "claude-sonnet-4-6"

    def __init__(self, data_path: str = "data/labs/research_experiments.json") -> None:
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


lab = ResearchLab()
