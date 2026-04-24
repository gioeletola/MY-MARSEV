"""
Skill index — queryable in-memory registry of all loaded skills.
"""
from __future__ import annotations

import logging
from typing import Iterator

from sovereign.skills.types import SkillDefinition, SkillStatus

logger = logging.getLogger(__name__)


class SkillIndex:
    """Queryable index of loaded SkillDefinitions."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        if skill.skill_id in self._skills:
            logger.debug("SkillIndex: overwriting %s", skill.skill_id)
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def enable(self, skill_id: str) -> bool:
        s = self._skills.get(skill_id)
        if s:
            s.enabled = True
            s.status = SkillStatus.ACTIVE
            return True
        return False

    def disable(self, skill_id: str) -> bool:
        s = self._skills.get(skill_id)
        if s:
            s.enabled = False
            s.status = SkillStatus.DISABLED
            return True
        return False

    def all(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def active(self) -> list[SkillDefinition]:
        return [s for s in self._skills.values() if s.enabled and s.status != SkillStatus.DISABLED]

    def by_tag(self, tag: str) -> list[SkillDefinition]:
        return [s for s in self._skills.values() if tag in s.tags]

    def __len__(self) -> int:
        return len(self._skills)

    def __iter__(self) -> Iterator[SkillDefinition]:
        return iter(self._skills.values())

    def to_dict_list(self) -> list[dict]:
        return [
            {
                "skill_id": s.skill_id,
                "name": s.name,
                "description": s.description,
                "version": s.version,
                "status": s.status.value,
                "enabled": s.enabled,
                "tags": s.tags,
                "tools": s.tools,
                "permissions": [p.value for p in s.permissions],
                "requires_approval": s.requires_approval,
                "author": s.author,
            }
            for s in self._skills.values()
        ]
