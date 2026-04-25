"""
Legacy Layer — long-term impact design and legacy stewardship.
"""
from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/memory/legacy.json")


@dataclass
class LegacyPillar:
    """One dimension of the user's intended legacy."""
    pillar_id: str
    name: str             # e.g. "Family", "Professional", "Community"
    vision: str           # long-form vision statement
    current_actions: list[str] = field(default_factory=list)
    milestones: list[str] = field(default_factory=list)
    impact_score: float = 0.0   # 0.0 – 1.0 estimated current impact


@dataclass
class LegacyPlan:
    """The user's full legacy architecture."""
    owner_id: str
    north_star: str       # one-sentence ultimate legacy statement
    pillars: dict[str, LegacyPillar] = field(default_factory=dict)
    annual_review_date: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: int = 0


class LegacyLayer:
    """
    Maintains the user's legacy architecture.

    Stores the north star, legacy pillars, and tracks current actions
    aligned with each pillar. Computes overall legacy alignment score.
    """

    DEFAULT_PILLARS = [
        ("family", "Family Legacy", "Build a loving, thriving family culture that outlasts me."),
        ("professional", "Professional Legacy", "Create lasting value in my field."),
        ("community", "Community Legacy", "Improve the community I live in and serve."),
        ("knowledge", "Knowledge Legacy", "Produce knowledge and insights that help others."),
        ("financial", "Financial Legacy", "Build intergenerational wealth and opportunity."),
    ]

    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._plan: LegacyPlan | None = None

    def load(self, owner_id: str) -> LegacyPlan:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text("utf-8"))
                pillars = {
                    k: LegacyPillar(**v)
                    for k, v in raw.get("pillars", {}).items()
                }
                self._plan = LegacyPlan(
                    owner_id=owner_id,
                    north_star=raw.get("north_star", ""),
                    pillars=pillars,
                    annual_review_date=raw.get("annual_review_date", ""),
                    created_at=raw.get("created_at", ""),
                    version=raw.get("version", 0),
                )
                return self._plan
            except Exception as exc:
                logger.warning("LegacyLayer load error: %s", exc)

        self._plan = self._fresh(owner_id)
        return self._plan

    def set_north_star(self, statement: str) -> None:
        self._require_plan().north_star = statement
        self._persist()

    def update_pillar(
        self,
        pillar_id: str,
        current_actions: list[str] | None = None,
        milestones: list[str] | None = None,
        impact_score: float | None = None,
    ) -> None:
        plan = self._require_plan()
        pillar = plan.pillars.get(pillar_id)
        if pillar is None:
            raise KeyError(f"Pillar '{pillar_id}' not found")
        if current_actions is not None:
            pillar.current_actions = current_actions
        if milestones is not None:
            pillar.milestones = milestones
        if impact_score is not None:
            pillar.impact_score = max(0.0, min(1.0, impact_score))
        self._persist()

    def overall_impact_score(self) -> float:
        plan = self._require_plan()
        if not plan.pillars:
            return 0.0
        return sum(p.impact_score for p in plan.pillars.values()) / len(plan.pillars)

    def alignment_actions(self) -> list[str]:
        """Return all current actions across all pillars."""
        plan = self._require_plan()
        actions = []
        for pillar in plan.pillars.values():
            actions.extend(pillar.current_actions)
        return actions

    def report(self) -> dict[str, Any]:
        plan = self._require_plan()
        return {
            "north_star": plan.north_star,
            "overall_impact_score": round(self.overall_impact_score(), 3),
            "pillars": {k: asdict(v) for k, v in plan.pillars.items()},
            "version": plan.version,
        }

    # ------------------------------------------------------------------

    def _fresh(self, owner_id: str) -> LegacyPlan:
        pillars = {
            pid: LegacyPillar(pillar_id=pid, name=name, vision=vision)
            for pid, name, vision in self.DEFAULT_PILLARS
        }
        plan = LegacyPlan(owner_id=owner_id, north_star="", pillars=pillars)
        self._persist(plan)
        return plan

    def _require_plan(self) -> LegacyPlan:
        if self._plan is None:
            raise RuntimeError("Call load() first")
        return self._plan

    def _persist(self, plan: LegacyPlan | None = None) -> None:
        p = plan or self._plan
        if p is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(asdict(p), indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("LegacyLayer persist failed: %s", exc)
