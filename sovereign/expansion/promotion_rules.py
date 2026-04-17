"""Promotion rules — sandbox → shadow → production lifecycle for new agents."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentLifecycleStage(str, Enum):
    SANDBOX = "sandbox"     # Runs in isolation, output not used
    SHADOW = "shadow"       # Runs in parallel with production, output compared
    CANARY = "canary"       # Serves 10% of traffic
    PRODUCTION = "production"
    RETIRED = "retired"


@dataclass
class AgentLifecycleRecord:
    agent_id: str
    stage: AgentLifecycleStage = AgentLifecycleStage.SANDBOX
    eval_score: float = 0.0
    shadow_accuracy: float = 0.0
    canary_error_rate: float = 0.0
    created_at: float = field(default_factory=time.time)
    promoted_at: float = 0.0
    history: list[str] = field(default_factory=list)


class PromotionRules:
    """
    Decides when an agent is ready to advance from sandbox → shadow → canary → production.

    Thresholds (configurable):
    - sandbox → shadow: eval_score >= 0.70
    - shadow → canary: shadow_accuracy >= 0.80
    - canary → production: canary_error_rate <= 0.05 (5%)
    """

    def __init__(
        self,
        sandbox_to_shadow_threshold: float = 0.70,
        shadow_to_canary_threshold: float = 0.80,
        canary_error_threshold: float = 0.05,
    ) -> None:
        self._s2sh = sandbox_to_shadow_threshold
        self._sh2c = shadow_to_canary_threshold
        self._c_err = canary_error_threshold
        self._records: dict[str, AgentLifecycleRecord] = {}

    def register(self, agent_id: str) -> AgentLifecycleRecord:
        rec = AgentLifecycleRecord(agent_id=agent_id)
        self._records[agent_id] = rec
        return rec

    def update_eval(self, agent_id: str, eval_score: float) -> None:
        if rec := self._records.get(agent_id):
            rec.eval_score = eval_score

    def update_shadow(self, agent_id: str, accuracy: float) -> None:
        if rec := self._records.get(agent_id):
            rec.shadow_accuracy = accuracy

    def update_canary(self, agent_id: str, error_rate: float) -> None:
        if rec := self._records.get(agent_id):
            rec.canary_error_rate = error_rate

    def evaluate_promotion(self, agent_id: str) -> tuple[bool, str]:
        rec = self._records.get(agent_id)
        if not rec:
            return False, "Agent not registered"

        if rec.stage == AgentLifecycleStage.SANDBOX:
            if rec.eval_score >= self._s2sh:
                return True, f"Promote to SHADOW (eval={rec.eval_score:.2f})"
            return False, f"eval_score {rec.eval_score:.2f} < {self._s2sh}"

        if rec.stage == AgentLifecycleStage.SHADOW:
            if rec.shadow_accuracy >= self._sh2c:
                return True, f"Promote to CANARY (shadow_acc={rec.shadow_accuracy:.2f})"
            return False, f"shadow_accuracy {rec.shadow_accuracy:.2f} < {self._sh2c}"

        if rec.stage == AgentLifecycleStage.CANARY:
            if rec.canary_error_rate <= self._c_err:
                return True, f"Promote to PRODUCTION (error_rate={rec.canary_error_rate:.2%})"
            return False, f"canary_error_rate {rec.canary_error_rate:.2%} > {self._c_err:.0%}"

        return False, f"Already in {rec.stage}"

    def promote(self, agent_id: str) -> AgentLifecycleStage | None:
        rec = self._records.get(agent_id)
        if not rec:
            return None
        ready, reason = self.evaluate_promotion(agent_id)
        if not ready:
            logger.info("Promotion blocked for %s: %s", agent_id, reason)
            return None
        stage_order = list(AgentLifecycleStage)
        idx = stage_order.index(rec.stage)
        if idx + 1 < len(stage_order):
            rec.stage = stage_order[idx + 1]
            rec.promoted_at = time.time()
            rec.history.append(f"{time.strftime('%Y-%m-%d')} → {rec.stage}")
            logger.info("Agent %s promoted to %s", agent_id, rec.stage)
        return rec.stage

    def rollback(self, agent_id: str) -> bool:
        rec = self._records.get(agent_id)
        if not rec:
            return False
        rec.stage = AgentLifecycleStage.SANDBOX
        rec.history.append(f"{time.strftime('%Y-%m-%d')} ↩ SANDBOX (rollback)")
        logger.warning("Agent %s rolled back to SANDBOX", agent_id)
        return True

    def production_agents(self) -> list[str]:
        return [aid for aid, r in self._records.items() if r.stage == AgentLifecycleStage.PRODUCTION]

    def snapshot(self) -> list[dict]:
        return [{
            "agent_id": r.agent_id, "stage": r.stage.value,
            "eval_score": r.eval_score, "shadow_accuracy": r.shadow_accuracy,
            "canary_error_rate": r.canary_error_rate,
        } for r in self._records.values()]
