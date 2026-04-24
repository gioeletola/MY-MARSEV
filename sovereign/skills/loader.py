"""
Skill loader — discovers and loads .toml skill pack files from the data/ directory.
"""
from __future__ import annotations

import logging
import pathlib
from typing import Iterator

from sovereign.skills.parser import parse_skill_file
from sovereign.skills.types import SkillDefinition

logger = logging.getLogger(__name__)

_DEFAULT_SKILLS_DIR = pathlib.Path(__file__).parent / "data"


def discover_skill_files(directory: pathlib.Path | None = None) -> list[pathlib.Path]:
    """Return all .toml files in the skills data directory."""
    d = directory or _DEFAULT_SKILLS_DIR
    if not d.exists():
        return []
    return sorted(d.glob("*.toml"))


def load_all_skills(directory: pathlib.Path | None = None) -> list[SkillDefinition]:
    """Load and parse every .toml skill in the data directory."""
    skills: list[SkillDefinition] = []
    for path in discover_skill_files(directory):
        skill = parse_skill_file(path)
        if skill is not None:
            skills.append(skill)
            logger.debug("SkillLoader: loaded %s (%s)", skill.skill_id, skill.status.value)
    logger.info("SkillLoader: loaded %d skills", len(skills))
    return skills


def iter_skills(directory: pathlib.Path | None = None) -> Iterator[SkillDefinition]:
    for path in discover_skill_files(directory):
        skill = parse_skill_file(path)
        if skill is not None:
            yield skill
