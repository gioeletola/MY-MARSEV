"""
Provisioning executor — runs a ProvisioningPlan step by step,
creating vaults, binding agents, enabling centers, and registering skills.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sovereign.provisioning.types import (
    ProvisioningPlan,
    ProvisioningResult,
    ProvisioningStatus,
)

logger = logging.getLogger(__name__)


class ProvisioningExecutor:
    def __init__(
        self,
        entity_registry: Any = None,
        vault_manager: Any = None,
        skill_manager: Any = None,
        agent_registry: Any = None,
    ) -> None:
        self._entity_registry = entity_registry
        self._vault_manager = vault_manager
        self._skill_manager = skill_manager
        self._agent_registry = agent_registry

    def execute(self, plan: ProvisioningPlan) -> ProvisioningResult:
        result = ProvisioningResult(
            business_id=plan.business_id,
            status=ProvisioningStatus.IN_PROGRESS,
        )
        t0 = time.time()

        # Step 1: Register entity
        try:
            if self._entity_registry:
                entity = self._entity_registry.register(
                    name=plan.profile.name,
                    category="business",
                    metadata={
                        "tier": plan.profile.tier.value,
                        "industry": plan.profile.industry,
                        "owner_id": plan.profile.owner_id,
                    },
                )
                result.entity_id = getattr(entity, "entity_id", plan.business_id)
            result.steps_completed.append("register_entity")
        except Exception as exc:
            result.steps_failed.append("register_entity")
            result.errors.append(f"register_entity: {exc}")

        # Step 2: Create vaults
        for vault_name in plan.vaults_to_create:
            try:
                if self._vault_manager:
                    vid = self._vault_manager.create_vault(
                        name=vault_name,
                        owner_id=plan.profile.owner_id,
                    )
                    result.vault_ids.append(str(vid))
                result.steps_completed.append(f"vault:{vault_name}")
            except Exception as exc:
                result.steps_failed.append(f"vault:{vault_name}")
                result.errors.append(f"vault:{vault_name}: {exc}")

        # Step 3: Enable skills
        for skill_id in plan.skills_to_enable:
            try:
                if self._skill_manager:
                    self._skill_manager.enable(skill_id)
                result.steps_completed.append(f"skill:{skill_id}")
            except Exception as exc:
                result.steps_failed.append(f"skill:{skill_id}")
                result.errors.append(f"skill:{skill_id}: {exc}")

        # Step 4: Bind agents (record in plan metadata; actual agent instances are runtime)
        result.steps_completed.append(f"agents_bound:{len(plan.agents_to_bind)}")
        result.steps_completed.append(f"centers_bound:{len(plan.centers_to_bind)}")

        result.duration_ms = (time.time() - t0) * 1000
        result.status = (
            ProvisioningStatus.COMPLETED
            if not result.steps_failed
            else ProvisioningStatus.FAILED
        )

        logger.info(
            "Provisioning %s: %s (%d steps, %d failed, %.0fms)",
            plan.business_id,
            result.status.value,
            len(result.steps_completed),
            len(result.steps_failed),
            result.duration_ms,
        )
        return result
