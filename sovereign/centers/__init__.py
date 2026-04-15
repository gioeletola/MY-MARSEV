"""
Operational Centers — SOVEREIGN AI OS.

Each center is a high-level coordination hub that aggregates related
domain chiefs and exposes a unified interface to the orchestrator.
"""
from sovereign.centers.business_center import BusinessCenter
from sovereign.centers.personal_center import PersonalCenter
from sovereign.centers.strategic_center import StrategicCenter

__all__ = ["BusinessCenter", "PersonalCenter", "StrategicCenter"]
