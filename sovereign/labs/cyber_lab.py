"""
CyberLab — security testing, vulnerability assessment, incident simulation.

IMPORTANT: requires_human_review=True — all outputs must be reviewed before action.
"""
from __future__ import annotations

from sovereign.labs.labs_framework import LabsFramework


class CyberLab(LabsFramework):
    """Experimental sandbox for cybersecurity testing and incident simulation."""

    lab_id: str = "cyber"
    lab_name: str = "Cyber Lab"
    description: str = (
        "Security testing, vulnerability assessment, penetration test planning, "
        "and incident simulation. All outputs require human review before execution."
    )

    agents: list[str] = [
        "security_sentinel",
        "incident_response",
        "permission_auditor",
    ]
    tools: list[str] = ["code_exec", "memory_tool"]

    dataset_description: str = (
        "CVE databases, security audit logs, incident post-mortems, "
        "permission matrices, threat intelligence feeds, and hardening guides."
    )
    benchmarks: dict[str, float] = {
        "vulnerability_detection_rate": 0.90,
        "false_positive_rate": 0.05,
        "incident_response_coverage": 0.85,
        "permission_audit_completeness": 0.95,
    }
    output_standards: dict[str, str] = {
        "vulnerability_report": "CVSS-scored findings with remediation steps",
        "incident_runbook": "Step-by-step response with escalation paths",
        "permission_audit": "Role/resource matrix with least-privilege recommendations",
        "threat_model": "STRIDE or PASTA model with mitigations",
    }
    requires_human_review: bool = True
    model: str = "claude-sonnet-4-6"
    experiment_templates = [
        {
            "name": "Vulnerability Scan — AI-Assisted vs Manual Assessment",
            "description": "Compare vulnerability detection rate between AI-assisted scanning and traditional manual security review.",
            "hypothesis": {
                "statement": "AI-assisted scanning detects ≥90% of vulnerabilities found by manual review with ≤5% false positives",
                "metric": "vulnerability_detection_rate",
                "success_threshold": 0.90,
                "baseline": 0.65,
            },
            "control_config": {"method": "manual_review"},
            "treatment_config": {"method": "ai_assisted", "scan_depth": "deep", "cve_feed": True},
            "tags": ["cyber", "vulnerability", "scanning"],
        },
        {
            "name": "Incident Response Drill — Mean Time to Contain",
            "description": "Measure mean time to contain a simulated breach under structured runbook vs ad-hoc response.",
            "hypothesis": {
                "statement": "Runbook-guided response reduces mean time to contain by ≥40% vs ad-hoc",
                "metric": "incident_response_coverage",
                "success_threshold": 0.85,
                "baseline": 0.55,
            },
            "control_config": {"response": "ad_hoc"},
            "treatment_config": {"response": "runbook_guided", "escalation_paths": 3, "drills_per_year": 4},
            "tags": ["cyber", "incident_response", "drill"],
        },
        {
            "name": "Least-Privilege Audit — Permission Sprawl Reduction",
            "description": "Measure reduction in over-privileged accounts after applying AI-recommended least-privilege policy.",
            "hypothesis": {
                "statement": "AI-generated least-privilege recommendations reduce over-privileged accounts by ≥50%",
                "metric": "permission_audit_completeness",
                "success_threshold": 0.95,
                "baseline": 0.70,
            },
            "control_config": {"policy": "existing"},
            "treatment_config": {"policy": "ai_recommended", "scope": "all_roles", "review_cycle_days": 90},
            "tags": ["cyber", "permissions", "least_privilege"],
        },
    ]

    def __init__(self, data_path: str = "data/labs/cyber_experiments.json") -> None:
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


lab = CyberLab()
