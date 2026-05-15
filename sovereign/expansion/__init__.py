"""Expansion engine — agent scaffolding, gap detection, capability promotion."""
from sovereign.expansion.capability_gap_detector import CapabilityGap, CapabilityGapDetector
from sovereign.expansion.agent_scaffolder import AgentScaffolder
from sovereign.expansion.agent_promoter import AgentPromoter
from sovereign.expansion.agent_tester import AgentTester
from sovereign.expansion.connector_builder import ConnectorBuilder

__all__ = [
    "CapabilityGap",
    "CapabilityGapDetector",
    "AgentScaffolder",
    "AgentPromoter",
    "AgentTester",
    "ConnectorBuilder",
]
