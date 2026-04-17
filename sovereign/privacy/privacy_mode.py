"""Privacy mode — restricts data egress and routes sensitive tasks to local models."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger(__name__)


class PrivacyLevel(IntEnum):
    PUBLIC = 0       # Normal operation, cloud models allowed
    PRIVATE = 1      # Sensitive topics → local model
    LOCKED = 2       # All compute local, no external calls
    PARANOID = 3     # No network, no logging, in-memory only


@dataclass
class PrivacyPolicy:
    level: PrivacyLevel = PrivacyLevel.PUBLIC
    allow_cloud_for_non_sensitive: bool = True
    log_inputs: bool = True
    log_outputs: bool = True
    strip_pii_from_logs: bool = False
    allowed_external_domains: list[str] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.allowed_external_domains is None:
            self.allowed_external_domains = ["api.anthropic.com"]


class PrivacyMode:
    def __init__(self) -> None:
        self._policy = PrivacyPolicy()
        self._active_level = PrivacyLevel.PUBLIC

    def set_level(self, level: PrivacyLevel) -> None:
        old = self._active_level
        self._active_level = level
        self._policy.level = level
        if level >= PrivacyLevel.PRIVATE:
            self._policy.strip_pii_from_logs = True
        if level >= PrivacyLevel.LOCKED:
            self._policy.allow_cloud_for_non_sensitive = False
            self._policy.log_inputs = False
            self._policy.log_outputs = False
        if level == PrivacyLevel.PARANOID:
            self._policy.allowed_external_domains = []
        logger.info("PrivacyMode: %s → %s", old.name, level.name)

    def is_cloud_allowed(self, is_sensitive: bool = False) -> bool:
        if self._active_level >= PrivacyLevel.LOCKED:
            return False
        if is_sensitive and self._active_level >= PrivacyLevel.PRIVATE:
            return False
        return True

    def is_logging_allowed(self) -> bool:
        return self._policy.log_inputs

    def should_strip_pii(self) -> bool:
        return self._policy.strip_pii_from_logs

    def is_external_domain_allowed(self, domain: str) -> bool:
        if self._active_level == PrivacyLevel.PARANOID:
            return False
        return domain in self._policy.allowed_external_domains

    @property
    def level(self) -> PrivacyLevel:
        return self._active_level

    @property
    def policy(self) -> PrivacyPolicy:
        return self._policy

    def status(self) -> dict:
        return {
            "level": self._active_level.name,
            "cloud_allowed": self.is_cloud_allowed(),
            "logging": self.is_logging_allowed(),
            "strip_pii": self.should_strip_pii(),
        }
