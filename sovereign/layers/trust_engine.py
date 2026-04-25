"""
Trust Engine Layer — multi-dimensional trust scoring for agents, tools, and data sources.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TrustProfile:
    """Trust profile for an entity (agent, tool, data source, person)."""
    entity_id: str
    entity_type: str       # "agent" | "tool" | "source" | "person"
    trust_score: float     # 0.0 – 1.0
    basis: str             # reasoning for score
    override: bool = False # if True, score was set manually
    history: list[float] = field(default_factory=list)


# Heuristic baselines
_BASELINES: dict[str, float] = {
    "memory_tool": 0.92,
    "code_exec": 0.80,
    "file_ops": 0.80,
    "cli_exec": 0.70,
    "web_search": 0.65,
    "browser": 0.60,
    "mcp": 0.55,
}

# Domain trust
_DOMAIN_TRUST: dict[str, float] = {
    "anthropic.com": 0.95,
    "github.com": 0.85,
    "wikipedia.org": 0.80,
    "arxiv.org": 0.85,
    "gov": 0.80,
}

_SUSPICIOUS_PATTERNS = [
    re.compile(r"ignore (previous|prior|above) instructions", re.I),
    re.compile(r"disregard (your|the) (system|instructions)", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"new (persona|role|identity)", re.I),
    re.compile(r"jailbreak", re.I),
]


class TrustEngineLayer:
    """
    Centralized trust scoring.

    - Scores tools, agents, and data sources
    - Flags suspicious content via pattern matching
    - Maintains trust history for calibration
    - Supports manual overrides for known entities
    """

    def __init__(self) -> None:
        self._profiles: dict[str, TrustProfile] = {}
        self._initialize_defaults()

    # ------------------------------------------------------------------

    def score_tool(self, tool_name: str) -> float:
        """Return trust score for a tool."""
        profile = self._profiles.get(tool_name)
        if profile:
            return profile.trust_score
        return _BASELINES.get(tool_name, 0.50)

    def score_source(self, url: str) -> float:
        """Heuristic trust score for a URL/domain."""
        url_lower = url.lower()
        for domain, score in _DOMAIN_TRUST.items():
            if domain in url_lower:
                return score
        if url_lower.startswith("https://"):
            return 0.60
        return 0.40

    def score_content(self, text: str) -> float:
        """
        Check content for prompt injection or suspicious patterns.
        Returns 0.0 – 1.0 (lower = more suspicious).
        """
        for pattern in _SUSPICIOUS_PATTERNS:
            if pattern.search(text):
                logger.warning("TrustEngine: suspicious pattern detected in content")
                return 0.10
        length = len(text)
        if length > 50_000:
            return 0.55   # very long content warrants more scrutiny
        return 0.85

    def score_agent(self, agent_id: str) -> float:
        """Return trust score for an agent."""
        profile = self._profiles.get(agent_id)
        if profile:
            return profile.trust_score
        # Internal agents default high trust
        return 0.88

    def set_trust(self, entity_id: str, entity_type: str, score: float, basis: str = "manual") -> None:
        """Manually override an entity's trust score."""
        score = max(0.0, min(1.0, score))
        existing = self._profiles.get(entity_id)
        history = existing.history + [score] if existing else [score]
        self._profiles[entity_id] = TrustProfile(
            entity_id=entity_id,
            entity_type=entity_type,
            trust_score=score,
            basis=basis,
            override=True,
            history=history,
        )
        logger.info("TrustEngine: set trust %s → %.2f (%s)", entity_id, score, basis)

    def update_from_outcome(self, entity_id: str, success: bool) -> float:
        """Bayesian-lite update: nudge score based on observed outcome."""
        profile = self._profiles.get(entity_id)
        if profile is None:
            return 0.80
        delta = 0.02 if success else -0.05
        new_score = max(0.0, min(1.0, profile.trust_score + delta))
        profile.history.append(new_score)
        profile.trust_score = new_score
        return new_score

    def get_profile(self, entity_id: str) -> TrustProfile | None:
        return self._profiles.get(entity_id)

    def report(self) -> dict[str, Any]:
        return {
            "profiles": len(self._profiles),
            "low_trust": [
                eid for eid, p in self._profiles.items() if p.trust_score < 0.5
            ],
        }

    # ------------------------------------------------------------------

    def _initialize_defaults(self) -> None:
        for tool, score in _BASELINES.items():
            self._profiles[tool] = TrustProfile(
                entity_id=tool,
                entity_type="tool",
                trust_score=score,
                basis="baseline",
            )
