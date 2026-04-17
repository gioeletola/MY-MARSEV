"""
Risk scoring engine for SOVEREIGN AI OS.

Produces a composite RiskScore across multiple dimensions using
keyword-based heuristics. No external dependencies required.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dimension weights (must sum to 1.0)
# ---------------------------------------------------------------------------

_DIMENSION_WEIGHTS: dict[str, float] = {
    "financial":    0.25,
    "operational":  0.20,
    "reputational": 0.15,
    "legal":        0.15,
    "security":     0.15,
    "strategic":    0.10,
}

# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------

_FINANCIAL_KEYWORDS = frozenset([
    "payment", "pay", "transfer", "bank", "wire", "invoice", "purchase",
    "buy", "sell", "trade", "invest", "investment", "fund", "crypto",
    "bitcoin", "withdraw", "deposit", "transaction", "charge", "billing",
    "expense", "cost", "price", "money", "cash", "revenue", "budget",
    "salary", "payroll", "tax", "loan", "debt", "credit", "debit",
])

_LEGAL_KEYWORDS = frozenset([
    "contract", "agreement", "terms", "legal", "law", "regulation",
    "compliance", "gdpr", "hipaa", "liability", "lawsuit", "court",
    "attorney", "lawyer", "intellectual property", "copyright", "patent",
    "trademark", "privacy", "consent", "disclosure", "audit",
])

_SECURITY_KEYWORDS = frozenset([
    "password", "credential", "secret", "key", "token", "auth", "authentication",
    "encrypt", "decrypt", "hash", "vulnerability", "exploit", "attack",
    "breach", "hack", "malware", "virus", "phishing", "injection",
    "xss", "csrf", "permission", "access control", "firewall", "certificate",
])

_REPUTATIONAL_KEYWORDS = frozenset([
    "public", "publish", "post", "tweet", "announce", "press release",
    "customer", "client", "partner", "media", "news", "brand", "social",
    "reputation", "review", "feedback", "complaint", "apology",
])

_OPERATIONAL_KEYWORDS = frozenset([
    "delete", "remove", "drop", "shutdown", "restart", "deploy",
    "migrate", "update", "upgrade", "rollback", "backup", "restore",
    "database", "production", "live", "critical", "emergency",
    "incident", "outage", "downtime",
])

_STRATEGIC_KEYWORDS = frozenset([
    "strategy", "roadmap", "acquisition", "merger", "partnership",
    "expansion", "market", "competitive", "pricing model", "pivot",
    "vision", "mission", "long-term", "growth",
])

# Action classes that carry inherent operational risk
_HIGH_RISK_ACTION_CLASSES = frozenset({"EXECUTE", "DEPLOY", "DELETE", "MIGRATE"})
_MEDIUM_RISK_ACTION_CLASSES = frozenset({"DRAFT", "WRITE", "UPDATE"})


# ---------------------------------------------------------------------------
# Enums & Dataclasses
# ---------------------------------------------------------------------------


class RiskDimension(str, Enum):
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    REPUTATIONAL = "reputational"
    LEGAL = "legal"
    SECURITY = "security"
    STRATEGIC = "strategic"


@dataclass
class RiskScore:
    """Composite risk assessment for a proposed agent action."""

    overall: float                   # [0.0, 1.0]
    dimensions: dict[str, float]     # dimension name → [0.0, 1.0]
    flags: list[str]                 # Human-readable risk descriptions
    recommended_action_class: str    # Suggested ceiling, e.g. "SUGGEST" or "EXECUTE"

    def is_high_risk(self, threshold: float = 0.7) -> bool:
        return self.overall >= threshold

    def is_low_risk(self, threshold: float = 0.3) -> bool:
        return self.overall < threshold


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RiskScoringEngine:
    """
    Keyword-heuristic risk scoring across six dimensions.

    Usage::

        engine = RiskScoringEngine()
        score = engine.score(
            objective="Transfer $500 to vendor account",
            action_class="EXECUTE",
            agent_id="finance-agent-1",
            context={"amount": 500},
        )
        print(score.overall, score.flags)
    """

    def score(
        self,
        objective: str,
        action_class: str,
        agent_id: str,
        context: dict[str, Any] | None = None,
    ) -> RiskScore:
        """
        Compute a RiskScore for the proposed action.

        Parameters
        ----------
        objective:    Natural-language description of the intended action.
        action_class: String label of the ActionClass (e.g. "EXECUTE").
        agent_id:     Identifier of the requesting agent.
        context:      Optional additional context dict for future extensions.
        """
        context = context or {}
        obj_lower = objective.lower()
        ac_upper = action_class.upper()

        dimensions: dict[str, float] = {
            "financial":    self._score_financial(obj_lower, ac_upper),
            "operational":  self._score_operational(obj_lower, ac_upper),
            "reputational": self._score_reputational(obj_lower, ac_upper),
            "legal":        self._score_legal(obj_lower),
            "security":     self._score_security(obj_lower, agent_id),
            "strategic":    self._score_strategic(obj_lower),
        }

        overall = sum(
            dimensions[dim] * weight
            for dim, weight in _DIMENSION_WEIGHTS.items()
        )
        overall = round(min(1.0, max(0.0, overall)), 4)

        flags = self._build_flags(dimensions, ac_upper, obj_lower, context)
        recommended = self._recommend_action_class(overall, ac_upper)

        score = RiskScore(
            overall=overall,
            dimensions={k: round(v, 4) for k, v in dimensions.items()},
            flags=flags,
            recommended_action_class=recommended,
        )
        logger.debug(
            "RiskScoringEngine: agent=%s overall=%.3f flags=%s",
            agent_id, overall, flags,
        )
        return score

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------

    def _score_financial(self, objective: str, action_class: str) -> float:
        """High when objective touches money AND is executable."""
        kw_hits = _keyword_density(objective, _FINANCIAL_KEYWORDS)
        base = min(1.0, kw_hits * 0.35)
        # Executing financial actions is significantly riskier
        if action_class in _HIGH_RISK_ACTION_CLASSES and kw_hits > 0:
            base = min(1.0, base + 0.45)
        # Look for explicit amounts — numbers preceded by currency symbols
        if re.search(r"[\$€£¥]\s*\d+|\d+\s*(?:usd|eur|gbp|btc)", objective):
            base = min(1.0, base + 0.25)
        return base

    def _score_operational(self, objective: str, action_class: str) -> float:
        """High for destructive or deployment actions."""
        kw_hits = _keyword_density(objective, _OPERATIONAL_KEYWORDS)
        base = min(1.0, kw_hits * 0.3)
        if action_class in _HIGH_RISK_ACTION_CLASSES:
            base = min(1.0, base + 0.4)
        elif action_class in _MEDIUM_RISK_ACTION_CLASSES:
            base = min(1.0, base + 0.15)
        return base

    def _score_reputational(self, objective: str, action_class: str) -> float:
        """High when publishing or communicating externally."""
        kw_hits = _keyword_density(objective, _REPUTATIONAL_KEYWORDS)
        base = min(1.0, kw_hits * 0.35)
        # External communications in execute mode raise the bar
        if action_class in _HIGH_RISK_ACTION_CLASSES and kw_hits > 0:
            base = min(1.0, base + 0.25)
        return base

    def _score_legal(self, objective: str) -> float:
        """High when legal or compliance terms are present."""
        kw_hits = _keyword_density(objective, _LEGAL_KEYWORDS)
        return min(1.0, kw_hits * 0.4)

    def _score_security(self, objective: str, agent_id: str) -> float:
        """High when credentials, keys, or attack vectors are mentioned."""
        kw_hits = _keyword_density(objective, _SECURITY_KEYWORDS)
        base = min(1.0, kw_hits * 0.4)
        # Agents with "security" or "admin" in their ID touching security topics
        if any(tag in agent_id.lower() for tag in ("admin", "root", "security")):
            base = min(1.0, base + 0.15)
        return base

    def _score_strategic(self, objective: str) -> float:
        """High for long-term or high-impact strategic actions."""
        kw_hits = _keyword_density(objective, _STRATEGIC_KEYWORDS)
        return min(1.0, kw_hits * 0.45)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_flags(
        dimensions: dict[str, float],
        action_class: str,
        objective: str,
        context: dict[str, Any],
    ) -> list[str]:
        flags: list[str] = []
        if dimensions["financial"] >= 0.5:
            flags.append("High financial risk: objective involves monetary operations")
        if dimensions["financial"] >= 0.8:
            flags.append("Critical financial risk: large monetary amount or high-impact financial action")
        if dimensions["operational"] >= 0.5:
            flags.append("Elevated operational risk: destructive or deployment action detected")
        if dimensions["security"] >= 0.5:
            flags.append("Security concern: credential, key, or vulnerability terms present")
        if dimensions["legal"] >= 0.5:
            flags.append("Legal/compliance exposure: regulatory or contractual terms found")
        if dimensions["reputational"] >= 0.5:
            flags.append("Reputational risk: external communication or publication likely")
        if dimensions["strategic"] >= 0.5:
            flags.append("Strategic impact: long-term or organisation-wide consequences possible")
        if action_class in _HIGH_RISK_ACTION_CLASSES:
            flags.append(f"Execution-class action '{action_class}' inherently requires elevated scrutiny")
        return flags

    @staticmethod
    def _recommend_action_class(overall: float, requested: str) -> str:
        """
        Suggest the safest action class ceiling for this risk level.
        Never recommends *higher* than requested.
        """
        if overall >= 0.8:
            return "READ"
        if overall >= 0.6:
            return "SUGGEST"
        if overall >= 0.4:
            return "DRAFT"
        return requested  # Low risk: honour the requested class


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _keyword_density(text: str, keywords: frozenset[str]) -> float:
    """
    Return a normalised hit count [0, N] — number of distinct keyword
    matches in *text*, not capped.  Callers are responsible for clamping.
    """
    return sum(1 for kw in keywords if kw in text)
