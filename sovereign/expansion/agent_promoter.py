"""Agent promoter — manages sandbox → shadow → production promotion lifecycle."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LEDGER_PATH = Path("data/memory/agent_promotion_ledger.json")


class AgentStage(str, Enum):
    SANDBOX    = "sandbox"    # unit-tested only, not in live traffic
    SHADOW     = "shadow"     # runs in parallel with prod agent, output compared
    PRODUCTION = "production" # fully active, handles real tasks
    RETIRED    = "retired"    # removed from service


@dataclass
class PromotionRecord:
    agent_id: str
    stage: AgentStage
    promoted_at: float
    promoted_by: str          # "auto" | human name
    test_pass_rate: float
    shadow_accuracy: float
    notes: str = ""


@dataclass
class AgentLifecycle:
    agent_id: str
    agent_class: str
    domain: str
    current_stage: AgentStage = AgentStage.SANDBOX
    history: list[PromotionRecord] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    shadow_comparisons: int = 0
    shadow_agreements: int = 0
    total_calls: int = 0
    error_rate: float = 0.0

    @property
    def shadow_accuracy(self) -> float:
        if self.shadow_comparisons == 0:
            return 0.0
        return self.shadow_agreements / self.shadow_comparisons


class AgentPromoter:
    """
    Manages agent lifecycle: sandbox → shadow → production.

    Promotion criteria (all must be met for auto-promotion):
    - Sandbox test pass rate ≥ min_pass_rate
    - Shadow accuracy ≥ min_shadow_accuracy  (shadow → prod)
    - min_shadow_calls shadow calls completed
    - No high-risk domain (financial agents require human review)
    """

    def __init__(
        self,
        policy: "SelfExpansionPolicy | None" = None,  # type: ignore[name-defined]
        min_pass_rate: float = 0.8,
        min_shadow_accuracy: float = 0.85,
        min_shadow_calls: int = 20,
    ) -> None:
        self._policy = policy
        self._min_pass_rate = min_pass_rate
        self._min_shadow_accuracy = min_shadow_accuracy
        self._min_shadow_calls = min_shadow_calls
        self._lifecycles: dict[str, AgentLifecycle] = {}
        self._load()

    # ------------------------------------------------------------------
    # Registration & tracking
    # ------------------------------------------------------------------

    def register(self, agent_id: str, agent_class: str, domain: str) -> AgentLifecycle:
        if agent_id not in self._lifecycles:
            lc = AgentLifecycle(agent_id=agent_id, agent_class=agent_class, domain=domain)
            self._lifecycles[agent_id] = lc
            self._save()
        return self._lifecycles[agent_id]

    def get(self, agent_id: str) -> AgentLifecycle | None:
        return self._lifecycles.get(agent_id)

    def record_shadow_comparison(self, agent_id: str, agreed: bool) -> None:
        lc = self._lifecycles.get(agent_id)
        if lc:
            lc.shadow_comparisons += 1
            if agreed:
                lc.shadow_agreements += 1
            self._save()

    # ------------------------------------------------------------------
    # Promotion logic
    # ------------------------------------------------------------------

    def try_promote(
        self,
        agent_id: str,
        test_pass_rate: float,
        promoted_by: str = "auto",
        notes: str = "",
    ) -> tuple[bool, str]:
        """Attempt to promote an agent to the next stage. Returns (success, reason)."""
        lc = self._lifecycles.get(agent_id)
        if not lc:
            return False, f"Unknown agent: {agent_id}"

        if lc.current_stage == AgentStage.RETIRED:
            return False, "Agent is retired"

        # Policy check
        if self._policy:
            allowed, reason = self._policy.check_promotion(
                agent_id=agent_id, domain=lc.domain,
                from_stage=lc.current_stage, promoted_by=promoted_by,
            )
            if not allowed:
                return False, f"Policy blocked: {reason}"

        if lc.current_stage == AgentStage.SANDBOX:
            if test_pass_rate < self._min_pass_rate:
                return False, f"Pass rate {test_pass_rate:.0%} < required {self._min_pass_rate:.0%}"
            return self._do_promote(lc, AgentStage.SHADOW, test_pass_rate, 0.0, promoted_by, notes)

        if lc.current_stage == AgentStage.SHADOW:
            if lc.shadow_comparisons < self._min_shadow_calls:
                return False, (
                    f"Need {self._min_shadow_calls} shadow calls, have {lc.shadow_comparisons}"
                )
            if lc.shadow_accuracy < self._min_shadow_accuracy:
                return False, (
                    f"Shadow accuracy {lc.shadow_accuracy:.0%} < required {self._min_shadow_accuracy:.0%}"
                )
            return self._do_promote(lc, AgentStage.PRODUCTION, test_pass_rate, lc.shadow_accuracy, promoted_by, notes)

        return False, f"No promotion path from {lc.current_stage.value}"

    def retire(self, agent_id: str, by: str = "admin") -> bool:
        lc = self._lifecycles.get(agent_id)
        if not lc:
            return False
        lc.current_stage = AgentStage.RETIRED
        lc.history.append(PromotionRecord(
            agent_id=agent_id, stage=AgentStage.RETIRED,
            promoted_at=time.time(), promoted_by=by,
            test_pass_rate=0.0, shadow_accuracy=0.0,
        ))
        self._save()
        logger.info("AgentPromoter: %s retired by %s", agent_id, by)
        return True

    def list_by_stage(self, stage: AgentStage) -> list[AgentLifecycle]:
        return [lc for lc in self._lifecycles.values() if lc.current_stage == stage]

    def snapshot(self) -> list[dict]:
        return [
            {
                "agent_id": lc.agent_id, "stage": lc.current_stage.value,
                "domain": lc.domain, "shadow_accuracy": round(lc.shadow_accuracy, 3),
                "total_calls": lc.total_calls,
            }
            for lc in self._lifecycles.values()
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _do_promote(
        self, lc: AgentLifecycle, to_stage: AgentStage,
        pass_rate: float, shadow_acc: float, by: str, notes: str,
    ) -> tuple[bool, str]:
        prev = lc.current_stage
        lc.current_stage = to_stage
        lc.history.append(PromotionRecord(
            agent_id=lc.agent_id, stage=to_stage,
            promoted_at=time.time(), promoted_by=by,
            test_pass_rate=pass_rate, shadow_accuracy=shadow_acc,
            notes=notes,
        ))
        self._save()
        msg = f"Promoted {lc.agent_id}: {prev.value} → {to_stage.value}"
        logger.info("AgentPromoter: %s", msg)
        return True, msg

    def _save(self) -> None:
        try:
            _LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for aid, lc in self._lifecycles.items():
                data[aid] = {
                    "agent_id": lc.agent_id, "agent_class": lc.agent_class,
                    "domain": lc.domain, "current_stage": lc.current_stage.value,
                    "created_at": lc.created_at, "shadow_comparisons": lc.shadow_comparisons,
                    "shadow_agreements": lc.shadow_agreements, "total_calls": lc.total_calls,
                    "error_rate": lc.error_rate,
                    "history": [
                        {"agent_id": r.agent_id, "stage": r.stage.value,
                         "promoted_at": r.promoted_at, "promoted_by": r.promoted_by,
                         "test_pass_rate": r.test_pass_rate, "shadow_accuracy": r.shadow_accuracy,
                         "notes": r.notes}
                        for r in lc.history
                    ],
                }
            _LEDGER_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("AgentPromoter save failed: %s", exc)

    def _load(self) -> None:
        if not _LEDGER_PATH.exists():
            return
        try:
            data = json.loads(_LEDGER_PATH.read_text(encoding="utf-8"))
            for aid, d in data.items():
                lc = AgentLifecycle(
                    agent_id=d["agent_id"], agent_class=d["agent_class"],
                    domain=d["domain"], current_stage=AgentStage(d["current_stage"]),
                    created_at=d.get("created_at", 0.0),
                    shadow_comparisons=d.get("shadow_comparisons", 0),
                    shadow_agreements=d.get("shadow_agreements", 0),
                    total_calls=d.get("total_calls", 0),
                    error_rate=d.get("error_rate", 0.0),
                )
                for r in d.get("history", []):
                    lc.history.append(PromotionRecord(
                        agent_id=r["agent_id"], stage=AgentStage(r["stage"]),
                        promoted_at=r["promoted_at"], promoted_by=r["promoted_by"],
                        test_pass_rate=r["test_pass_rate"], shadow_accuracy=r["shadow_accuracy"],
                        notes=r.get("notes", ""),
                    ))
                self._lifecycles[aid] = lc
        except Exception as exc:
            logger.warning("AgentPromoter load failed: %s", exc)
