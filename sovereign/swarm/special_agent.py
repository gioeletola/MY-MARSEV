"""
Special Agents — trust scoring, risk engine, anomaly detector, prompt optimizer.
"""
from __future__ import annotations

import re
from typing import Any

from sovereign.output.output_contract import OutputStatus, StructuredOutput
from sovereign.swarm.base_agent import AgentContext, AgentTask, BaseAgent


class TrustScoringAgent(BaseAgent):
    """
    Scores the trustworthiness of information sources and agent outputs.

    Scoring is heuristic-first (fast, no API call) with optional Claude
    deep-assessment for ambiguous cases.

    Score bands:
      0.9-1.0  Trusted internal memory / verified source
      0.7-0.9  Reputable external source (known domain)
      0.5-0.7  Unknown / unverified source
      0.3-0.5  Suspicious indicators present
      0.0-0.3  Likely untrustworthy / contradictory
    """

    agent_id = "trust_scorer"
    model = "claude-haiku-4-5-20251001"

    # Domains known to be reputable (extend as needed)
    _TRUSTED_DOMAINS = frozenset({
        "gov", "edu", "wikipedia.org", "reuters.com", "bbc.com",
        "nature.com", "arxiv.org", "pubmed.ncbi.nlm.nih.gov",
        "sec.gov", "eur-lex.europa.eu", "legislation.gov.uk",
    })
    _SUSPICIOUS_PATTERNS = re.compile(
        r"(fake|scam|hoax|conspiracy|unverified|rumour|rumor)", re.IGNORECASE
    )

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """
        task.objective should be the source descriptor:
          "url:https://reuters.com/...", "memory:research:key123",
          "agent:worker:output", or plain text snippet.
        """
        source = task.objective
        score, rationale = self._heuristic_score(source)

        # If score is ambiguous (0.4-0.7), ask Claude for deeper assessment
        if 0.4 <= score <= 0.7:
            score, rationale = await self._deep_assess(source, score, ctx)

        return self._make_output(
            task=task, ctx=ctx,
            result=f"Trust score: {score:.2f} — {rationale}",
            status=OutputStatus.SUCCESS,
            data={"trust_score": round(score, 3), "rationale": rationale},
            confidence=0.85,
        )

    def score_source(self, source: str) -> float:
        """Synchronous quick-score for use in the input pipeline."""
        score, _ = self._heuristic_score(source)
        return score

    def _heuristic_score(self, source: str) -> tuple[float, str]:
        """Fast heuristic scoring — no API call."""
        src = source.lower()

        # Internal memory — fully trusted
        if src.startswith("memory:"):
            return 0.92, "Internal memory source — high trust."

        # Agent output — moderate trust (validated by guardian)
        if src.startswith("agent:"):
            return 0.78, "Agent output — reviewed by guardian."

        # URL-based scoring
        if src.startswith("url:") or src.startswith("http"):
            url = src.replace("url:", "").strip()
            for domain in self._TRUSTED_DOMAINS:
                if domain in url:
                    return 0.88, f"Reputable domain ({domain}) detected."
            if self._SUSPICIOUS_PATTERNS.search(url):
                return 0.25, "Suspicious URL pattern detected."
            return 0.60, "Unknown external URL — moderate trust."

        # Suspicious content patterns
        if self._SUSPICIOUS_PATTERNS.search(source):
            return 0.30, "Suspicious content pattern detected."

        # Default: unclassified
        return 0.65, "Unclassified source — default moderate trust."

    async def _deep_assess(
        self, source: str, initial_score: float, ctx: AgentContext
    ) -> tuple[float, str]:
        """Use Claude (Haiku) for deeper trust assessment on ambiguous sources."""
        prompt = (
            f"Rate the trustworthiness of this information source on a scale 0.0-1.0.\n\n"
            f"Source: {source[:500]}\n"
            f"Initial heuristic score: {initial_score}\n\n"
            f"Reply with JSON only: {{\"score\": 0.0, \"rationale\": \"...\"}}"
        )
        try:
            raw = await self._call_claude(
                [{"role": "user", "content": prompt}], ctx, max_tokens=100
            )
            import json
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            return float(data["score"]), str(data["rationale"])
        except Exception:
            return initial_score, "Deep assessment failed — using heuristic score."


class RiskEngineAgent(BaseAgent):
    """Scores risk for proposed actions. Used by GuardianAgent."""

    agent_id = "risk_engine"
    model = "claude-sonnet-4-6"

    # Risk keywords that bump score significantly
    _HIGH_RISK = re.compile(
        r"\b(delete|destroy|drop|truncate|format|wipe|overwrite|irreversible"
        r"|payment|transfer|wire|send money|purchase|buy|sell|trade"
        r"|publish|deploy|execute|run|launch|submit)\b",
        re.IGNORECASE,
    )
    _LOW_RISK = re.compile(
        r"\b(read|list|show|display|search|find|analyse|summarize|draft|review)\b",
        re.IGNORECASE,
    )

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        score, rationale = self._score(task.objective, task.action_class.name)
        return self._make_output(
            task=task, ctx=ctx,
            result=f"Risk score: {score:.2f} — {rationale}",
            status=OutputStatus.SUCCESS,
            data={"risk_score": round(score, 3), "rationale": rationale},
            confidence=0.80,
        )

    def _score(self, objective: str, action_class: str) -> tuple[float, str]:
        base = {"READ": 0.1, "SUGGEST": 0.2, "DRAFT": 0.35, "EXECUTE": 0.55}.get(
            action_class, 0.4
        )
        if self._HIGH_RISK.search(objective):
            base = min(base + 0.35, 1.0)
            return base, "High-risk keywords detected in objective."
        if self._LOW_RISK.search(objective):
            base = max(base - 0.15, 0.0)
            return base, "Low-risk read/analyse operation."
        return base, f"Baseline risk for {action_class} action class."


class AnomalyDetectorAgent(BaseAgent):
    """Detects anomalous patterns in agent behaviour or tool outputs."""

    agent_id = "anomaly_detector"
    model = "claude-haiku-4-5-20251001"

    _ANOMALY_PATTERNS = re.compile(
        r"(ignore previous|you are now|jailbreak|bypass|override instructions"
        r"|disregard your|forget your|system prompt|act as)",
        re.IGNORECASE,
    )

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        text = task.objective
        anomalies: list[dict[str, Any]] = []

        # Check for prompt injection / jailbreak attempts
        if self._ANOMALY_PATTERNS.search(text):
            anomalies.append({
                "type": "prompt_injection",
                "severity": "high",
                "snippet": text[:100],
            })

        # Check for unusually long inputs (possible padding attack)
        if len(text) > 50_000:
            anomalies.append({
                "type": "oversized_input",
                "severity": "medium",
                "length": len(text),
            })

        return self._make_output(
            task=task, ctx=ctx,
            result=f"{len(anomalies)} anomaly/anomalies detected." if anomalies
                   else "No anomalies detected.",
            status=OutputStatus.SUCCESS,
            data={"anomalies": anomalies, "count": len(anomalies)},
            confidence=0.90,
        )


class PromptOptimizerAgent(BaseAgent):
    """Suggests improvements to agent prompts based on evaluation results."""

    agent_id = "prompt_optimizer"
    model = "claude-sonnet-4-6"

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        prompt = (
            "You are the Prompt Optimizer of the SOVEREIGN AI OS.\n\n"
            "Analyse this agent prompt/output and suggest concrete improvements:\n\n"
            f"{task.objective}\n\n"
            "Focus on: clarity, specificity, output format, tool guidance, "
            "edge case handling. Provide 3-5 numbered suggestions."
        )
        result = await self._call_claude(
            [{"role": "user", "content": prompt}], ctx, task=task, max_tokens=600
        )
        return self._make_output(
            task=task, ctx=ctx, result=result,
            status=OutputStatus.SUCCESS,
            data={"suggestions_generated": True},
            confidence=0.75,
        )
