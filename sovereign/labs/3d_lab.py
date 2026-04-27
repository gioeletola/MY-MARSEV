"""ThreeDLab — 3D design, spatial modeling, and virtual environment concepts."""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class ThreeDLab(LabsFramework):
    lab_id = "3d"
    lab_name = "3D Lab"
    description = "3D design concepts, spatial modeling, virtual environment planning, and spatial aesthetics."
    agents = ["concept_lab", "aesthetic_direction", "empire_aesthetic"]
    tools = ["memory_tool", "file_ops"]
    dataset_description = "3D design references, spatial blueprints, environment concepts, model specifications."
    benchmarks = {"concept_clarity": 0.80, "spatial_coherence": 0.75}
    output_standards = {"3d_brief": "Spatial design brief with dimensions, aesthetics, and functional requirements"}
    requires_human_review = False
    model = "claude-sonnet-4-6"
    experiment_templates = [
        {
            "name": "3D Lab — Spatial Layout A/B",
            "description": "Compare zone-based vs open-plan spatial layouts.",
            "hypothesis": {"statement": "Zone-based layout improves spatial coherence",
                           "metric": "spatial_coherence", "success_threshold": 0.80, "baseline": 0.60},
            "control_config": {"layout": "open_plan"}, "treatment_config": {"layout": "zone_based"},
            "tags": ["3d", "spatial"],
        },
        {
            "name": "3D Lab — Material Palette Optimisation",
            "description": "Curated materials vs defaults for visual quality.",
            "hypothesis": {"statement": "Curated palette improves concept clarity",
                           "metric": "concept_clarity", "success_threshold": 0.82, "baseline": 0.65},
            "control_config": {"materials": "default"}, "treatment_config": {"materials": "curated_minimal"},
            "tags": ["3d", "aesthetics"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/3d_experiments.json") -> None:
        super().__init__(data_path=data_path)

    def describe(self) -> dict:
        return {"lab_id": self.lab_id, "lab_name": self.lab_name, "agents": self.agents,
                "tools": self.tools, "requires_human_review": self.requires_human_review, "model": self.model}

lab = ThreeDLab()
