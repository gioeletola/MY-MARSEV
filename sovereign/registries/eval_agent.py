"""EvalAgent — reads negative feedback and suggests prompt improvements."""
from __future__ import annotations

import logging
import os
from typing import Any

from sovereign.registries.agent_feedback import AgentFeedbackRegistry

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv("SOVEREIGN_EVAL_MODEL", "claude-haiku-4-5-20251001")


class EvalAgent:
    """Analyses thumbs-down feedback and proposes prompt patches.

    Run periodically (e.g. weekly via the scheduler) or on demand.
    For each agent with an average score below ``threshold``, it asks Claude
    to suggest a concrete instruction improvement based on the negative
    feedback comments.
    """

    def __init__(
        self,
        feedback_registry: AgentFeedbackRegistry | None = None,
        threshold: float = -0.2,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        self._registry = feedback_registry or AgentFeedbackRegistry()
        self._threshold = threshold
        self._model = model

    async def run(self) -> list[dict[str, Any]]:
        """Analyse poor-performing agents and return improvement suggestions.

        Returns a list of ``{agent_id, score, count, suggestion}`` dicts.
        """
        poor = self._registry.poor_agents(threshold=self._threshold)
        if not poor:
            logger.info("EvalAgent: no agents below threshold=%.2f", self._threshold)
            return []

        results: list[dict[str, Any]] = []
        for entry in poor:
            agent_id = entry["agent_id"]
            score    = entry["score"]
            comments = self._get_negative_comments(agent_id)
            suggestion = await self._generate_suggestion(agent_id, score, comments)
            results.append({
                "agent_id":   agent_id,
                "score":      score,
                "count":      entry["count"],
                "suggestion": suggestion,
            })
            logger.info(
                "EvalAgent: suggestion generated for agent=%s score=%.2f",
                agent_id, score,
            )
        return results

    def _get_negative_comments(self, agent_id: str, limit: int = 10) -> list[str]:
        records = self._registry._load()
        return [
            r["comment"]
            for r in records
            if r.get("agent_id") == agent_id
            and r.get("rating", 0) < 0
            and r.get("comment")
        ][:limit]

    async def _generate_suggestion(self, agent_id: str, score: float, comments: list[str]) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "Set ANTHROPIC_API_KEY to enable automated suggestions."
        comments_text = (
            "\n".join(f"- {c}" for c in comments)
            if comments
            else "No specific comments provided."
        )
        prompt = (
            f"Agent '{agent_id}' has an average user rating of {score:.2f} (-1=worst, +1=best).\n\n"
            f"Negative feedback:\n{comments_text}\n\n"
            "Suggest ONE specific, actionable improvement to the agent's system prompt "
            "or instructions. Give exact wording changes or new instructions to add. "
            "Keep it under 100 words."
        )
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            message = await client.messages.create(
                model=self._model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip()
        except Exception as exc:
            logger.error("EvalAgent: API call failed: %s", exc)
            return f"Could not generate suggestion: {exc}"

    async def report_to_memory(self, memory: Any, results: list[dict[str, Any]]) -> None:
        """Persist eval results to the learning memory domain."""
        import datetime
        now = datetime.datetime.utcnow().isoformat() + "Z"
        for r in results:
            key = f"eval_{r['agent_id']}_{now[:10]}"
            await memory.write("learning", key, {**r, "created_at": now})
