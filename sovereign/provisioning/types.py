"""Business provisioning data types."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProvisioningStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class BusinessTier(str, Enum):
    SOLO = "solo"          # 1 user, basic centers
    STARTUP = "startup"    # 2-10 users, full centers
    SCALE = "scale"        # 11-50 users, all centers + labs
    ENTERPRISE = "enterprise"


@dataclass
class BusinessProfile:
    name: str
    tier: BusinessTier = BusinessTier.SOLO
    industry: str = "general"
    owner_id: str = "owner"
    locale: str = "en"
    timezone: str = "UTC"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProvisioningPlan:
    business_id: str
    profile: BusinessProfile
    centers_to_bind: list[str] = field(default_factory=list)
    agents_to_bind: list[str] = field(default_factory=list)
    vaults_to_create: list[str] = field(default_factory=list)
    connectors_to_enable: list[str] = field(default_factory=list)
    skills_to_enable: list[str] = field(default_factory=list)


@dataclass
class ProvisioningResult:
    business_id: str
    status: ProvisioningStatus = ProvisioningStatus.PENDING
    steps_completed: list[str] = field(default_factory=list)
    steps_failed: list[str] = field(default_factory=list)
    entity_id: str = ""
    vault_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
