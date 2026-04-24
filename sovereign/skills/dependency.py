"""
Skill dependency resolver — topological sort and availability checks.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sovereign.skills.types import SkillDefinition

logger = logging.getLogger(__name__)


def resolve_execution_order(
    skills: list["SkillDefinition"],
    registry: dict[str, "SkillDefinition"],
) -> list["SkillDefinition"]:
    """
    Return skills in dependency-safe execution order (topological sort).
    Raises ValueError on circular dependencies.
    """
    ordered: list[SkillDefinition] = []
    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(s: "SkillDefinition") -> None:
        if s.skill_id in visiting:
            raise ValueError(f"Circular dependency detected for skill: {s.skill_id}")
        if s.skill_id in visited:
            return
        visiting.add(s.skill_id)
        for dep in s.dependencies:
            dep_skill = registry.get(dep.skill_id)
            if dep_skill is None:
                if dep.optional:
                    logger.debug("SkillDep: optional dep %s not found for %s", dep.skill_id, s.skill_id)
                    continue
                raise ValueError(f"Skill {s.skill_id!r} requires missing dependency {dep.skill_id!r}")
            visit(dep_skill)
        visiting.discard(s.skill_id)
        visited.add(s.skill_id)
        ordered.append(s)

    for skill in skills:
        visit(skill)
    return ordered


def check_dependencies_met(
    skill: "SkillDefinition",
    registry: dict[str, "SkillDefinition"],
) -> tuple[bool, list[str]]:
    """Return (all_met, list_of_missing_ids)."""
    missing = []
    for dep in skill.dependencies:
        dep_skill = registry.get(dep.skill_id)
        if dep_skill is None and not dep.optional:
            missing.append(dep.skill_id)
        elif dep_skill is not None and not dep_skill.enabled:
            missing.append(dep.skill_id)
    return len(missing) == 0, missing
