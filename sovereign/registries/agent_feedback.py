"""Agent feedback registry — records thumbs up/down per agent, surfaces to prompt tuning."""
from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any


_DEFAULT_PATH = pathlib.Path("data/memory/agent_feedback.json")


class AgentFeedbackRegistry:
    """Persist and query user feedback (thumbs up/down) for each agent.

    Feedback is stored as a JSON list in *data/memory/agent_feedback.json*.
    The file is created automatically on first write if it does not exist.
    """

    def __init__(self, path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> list[dict[str, Any]]:
        """Load the feedback list from disk, returning [] when absent."""
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, records: list[dict[str, Any]]) -> None:
        """Write the feedback list to disk, creating parent dirs as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        agent_id: str,
        session_id: str,
        task_id: str,
        rating: int,
        comment: str = "",
    ) -> None:
        """Append a feedback entry.

        Args:
            agent_id:   Identifier of the agent that produced the response.
            session_id: Current session identifier.
            task_id:    Task / message identifier.
            rating:     +1 (thumbs up) or -1 (thumbs down).
            comment:    Optional free-text comment.
        """
        if rating not in (1, -1):
            raise ValueError(f"rating must be +1 or -1, got {rating!r}")

        records = self._load()
        records.append(
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "task_id": task_id,
                "rating": rating,
                "comment": comment,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            }
        )
        self._save(records)

    def agent_score(self, agent_id: str) -> float:
        """Return the average rating for *agent_id* in the range [-1.0, +1.0].

        Returns 0.0 when no feedback exists for the agent.
        """
        records = self._load()
        relevant = [r["rating"] for r in records if r.get("agent_id") == agent_id]
        if not relevant:
            return 0.0
        return sum(relevant) / len(relevant)

    def top_agents(self, n: int = 10) -> list[dict[str, Any]]:
        """Return the top *n* agents sorted by descending average score.

        Each element is ``{"agent_id": str, "score": float, "count": int}``.
        """
        records = self._load()
        by_agent: dict[str, list[int]] = {}
        for r in records:
            aid = r.get("agent_id", "unknown")
            by_agent.setdefault(aid, []).append(r.get("rating", 0))

        ranked = sorted(
            [
                {
                    "agent_id": aid,
                    "score": sum(ratings) / len(ratings),
                    "count": len(ratings),
                }
                for aid, ratings in by_agent.items()
            ],
            key=lambda x: x["score"],
            reverse=True,
        )
        return ranked[:n]

    def poor_agents(self, threshold: float = -0.3) -> list[dict[str, Any]]:
        """Return agents whose average score is below *threshold*.

        Each element is ``{"agent_id": str, "score": float, "count": int}``.
        """
        records = self._load()
        by_agent: dict[str, list[int]] = {}
        for r in records:
            aid = r.get("agent_id", "unknown")
            by_agent.setdefault(aid, []).append(r.get("rating", 0))

        return [
            {
                "agent_id": aid,
                "score": sum(ratings) / len(ratings),
                "count": len(ratings),
            }
            for aid, ratings in by_agent.items()
            if sum(ratings) / len(ratings) < threshold
        ]

    def summary(self) -> dict[str, Any]:
        """Return a summary dict for dashboard display.

        Keys:
            total_feedback  — total number of feedback records.
            agents_rated    — distinct agent IDs that received feedback.
            top_3           — top 3 agents by score.
            needs_attention — agents below the -0.3 threshold.
        """
        records = self._load()
        total = len(records)
        agents_rated = len({r.get("agent_id") for r in records})
        top_3 = self.top_agents(n=3)
        needs_attention = self.poor_agents(threshold=-0.3)
        return {
            "total_feedback": total,
            "agents_rated": agents_rated,
            "top_3": top_3,
            "needs_attention": needs_attention,
        }
