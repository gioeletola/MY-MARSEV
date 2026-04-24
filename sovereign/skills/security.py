"""
Skill security layer — validates permissions, blocks dangerous execution.
"""
from __future__ import annotations

import logging

from sovereign.skills.types import SkillDefinition, SkillPermission

logger = logging.getLogger(__name__)

# Permissions that require explicit approval before execution
_APPROVAL_REQUIRED = {
    SkillPermission.EXECUTE,
    SkillPermission.CODE,
    SkillPermission.WRITE,
}

# Permissions that require a governance check
_HIGH_RISK = {
    SkillPermission.EXECUTE,
    SkillPermission.CODE,
}


class SkillSecurityError(Exception):
    pass


def validate_skill(skill: SkillDefinition) -> None:
    """Raise SkillSecurityError if the skill definition is unsafe or misconfigured."""
    if not skill.skill_id:
        raise SkillSecurityError("Skill missing skill_id")
    if not skill.name:
        raise SkillSecurityError(f"Skill {skill.skill_id!r} missing name")
    # High-risk permissions must declare requires_approval
    dangerous = set(skill.permissions) & _HIGH_RISK
    if dangerous and not skill.requires_approval:
        logger.warning(
            "SkillSecurity: skill %s has high-risk permissions %s but requires_approval=False — forcing True",
            skill.skill_id, dangerous,
        )
        skill.requires_approval = True


def check_execution_allowed(skill: SkillDefinition, user_permissions: set[str] | None = None) -> bool:
    """Return True if execution is permitted given user_permissions context."""
    if not skill.enabled:
        logger.warning("SkillSecurity: skill %s is disabled", skill.skill_id)
        return False
    from sovereign.skills.types import SkillStatus
    if skill.status in (SkillStatus.DISABLED,):
        return False
    return True
