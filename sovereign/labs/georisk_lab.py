"""
GeoRiskLab — geopolitical risk analysis, jurisdiction risk.
"""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class GeoRiskLab(LabsFramework):
    """Experimental sandbox for geopolitical risk and jurisdiction analysis."""

    lab_id: str = "georisk"
    lab_name: str = "GeoRisk Lab"
    description: str = (
        "Geopolitical risk analysis, jurisdiction risk scoring, "
        "cross-border regulatory mapping, and political stability assessments."
    )

    agents: list[str] = [
        "blackmap_georisk",
    ]
    tools: list[str] = ["web_search", "memory_tool"]

    dataset_description: str = (
        "Geopolitical risk indices, country risk ratings, regulatory databases, "
        "sanctions lists, news feeds, and historical political event data."
    )
    benchmarks: dict[str, float] = {
        "risk_signal_accuracy": 0.80,
        "jurisdiction_coverage": 0.90,
        "early_warning_lead_time_days": 14.0,
        "regulatory_mapping_completeness": 0.85,
    }
    output_standards: dict[str, str] = {
        "country_risk_brief": "Risk score, drivers, and 90-day outlook per jurisdiction",
        "geopolitical_alert": "Event summary with impact assessment and recommended actions",
        "jurisdiction_matrix": "Comparative risk table across target geographies",
        "regulatory_map": "Key regulations, enforcement history, and compliance requirements",
    }
    requires_human_review: bool = False
    model: str = "claude-sonnet-4-6"
    experiment_templates = [
        {
            "name": "Country Risk Scoring — AI Model vs Commercial Index",
            "description": "Compare AI-generated country risk scores against established commercial indices (EIU, PRS) across 20 markets.",
            "hypothesis": {
                "statement": "AI country risk scores correlate ≥0.80 with commercial index rankings",
                "metric": "risk_signal_accuracy",
                "success_threshold": 0.80,
                "baseline": 0.55,
            },
            "control_config": {"source": "commercial_index"},
            "treatment_config": {"source": "ai_model", "data_feeds": ["news", "regulatory", "economic", "political"]},
            "tags": ["georisk", "country_risk", "scoring"],
        },
        {
            "name": "Early Warning System — Geopolitical Event Lead Time",
            "description": "Measure how many days before a geopolitical event the SOVEREIGN OS raises a risk alert.",
            "hypothesis": {
                "statement": "Multi-signal monitoring provides ≥14-day early warning for 80% of major geopolitical events",
                "metric": "early_warning_lead_time_days",
                "success_threshold": 14.0,
                "baseline": 3.0,
            },
            "control_config": {"monitoring": "manual_news"},
            "treatment_config": {"monitoring": "automated_multi_signal", "signals": ["sanctions", "election", "protest", "trade"]},
            "tags": ["georisk", "early_warning", "geopolitical"],
        },
        {
            "name": "Regulatory Mapping Coverage — Jurisdiction Completeness Audit",
            "description": "Audit completeness of regulatory mapping across 30 target jurisdictions compared to ground-truth legal database.",
            "hypothesis": {
                "statement": "AI regulatory mapping achieves ≥85% coverage of material regulations per jurisdiction",
                "metric": "regulatory_mapping_completeness",
                "success_threshold": 0.85,
                "baseline": 0.60,
            },
            "control_config": {"method": "manual_legal_review"},
            "treatment_config": {"method": "ai_regulatory_scan", "jurisdictions": 30, "update_frequency": "weekly"},
            "tags": ["georisk", "regulatory", "compliance"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/georisk_experiments.json") -> None:
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


lab = GeoRiskLab()
