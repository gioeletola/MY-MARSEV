"""
Skill manager — top-level façade for loading, querying, enabling, disabling and executing skills.
"""
from __future__ import annotations

import logging
import pathlib
from typing import Any

from sovereign.skills.dependency import check_dependencies_met
from sovereign.skills.executor import SkillExecutor
from sovereign.skills.index import SkillIndex
from sovereign.skills.loader import load_all_skills
from sovereign.skills.security import validate_skill, SkillSecurityError
from sovereign.skills.types import SkillDefinition, SkillExecutionResult

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = pathlib.Path(__file__).parent / "data"


class SkillManager:
    """
    Central skills runtime.

    Usage::
        manager = SkillManager()
        manager.load()                         # scan data/*.toml
        manager.enable("email-draft")
        result = await manager.execute("email-draft", {"subject": "Hello"})
    """

    def __init__(
        self,
        data_dir: pathlib.Path | None = None,
        orchestrator: Any = None,
        tool_registry: Any = None,
    ) -> None:
        self._data_dir = data_dir or _DEFAULT_DATA_DIR
        self._index = SkillIndex()
        self._executor = SkillExecutor(orchestrator=orchestrator, tool_registry=tool_registry)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, directory: pathlib.Path | None = None) -> int:
        """Scan and load all .toml skill packs. Returns number loaded."""
        skills = load_all_skills(directory or self._data_dir)
        for skill in skills:
            try:
                validate_skill(skill)
                self._index.register(skill)
            except SkillSecurityError as exc:
                logger.warning("SkillManager: skipping invalid skill %s: %s", skill.skill_id, exc)
        logger.info("SkillManager: %d skills available", len(self._index))
        return len(self._index)

    def register(self, skill: SkillDefinition) -> None:
        """Register a skill programmatically (e.g. from Python code)."""
        validate_skill(skill)
        self._index.register(skill)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def enable(self, skill_id: str) -> bool:
        ok = self._index.enable(skill_id)
        if ok:
            logger.info("SkillManager: enabled %s", skill_id)
        return ok

    def disable(self, skill_id: str) -> bool:
        ok = self._index.disable(skill_id)
        if ok:
            logger.info("SkillManager: disabled %s", skill_id)
        return ok

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._index.get(skill_id)

    def list_all(self) -> list[dict]:
        return self._index.to_dict_list()

    def list_active(self) -> list[SkillDefinition]:
        return self._index.active()

    def list_by_tag(self, tag: str) -> list[SkillDefinition]:
        return self._index.by_tag(tag)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        skill_id: str,
        inputs: dict[str, Any] | None = None,
        session_id: str = "skill",
    ) -> SkillExecutionResult:
        skill = self._index.get(skill_id)
        if skill is None:
            return SkillExecutionResult(
                skill_id=skill_id, success=False,
                error=f"Skill {skill_id!r} not found in registry",
            )
        # Dependency check
        ok, missing = check_dependencies_met(skill, {s.skill_id: s for s in self._index})
        if not ok:
            return SkillExecutionResult(
                skill_id=skill_id, success=False,
                error=f"Missing skill dependencies: {missing}",
            )
        return await self._executor.execute(skill, inputs or {}, session_id)

    # ------------------------------------------------------------------
    # Admin helpers
    # ------------------------------------------------------------------

    def health(self) -> dict:
        skills = self._index.all()
        return {
            "total": len(skills),
            "active": sum(1 for s in skills if s.enabled),
            "disabled": sum(1 for s in skills if not s.enabled),
            "requires_approval": sum(1 for s in skills if s.requires_approval),
        }

    def wire_orchestrator(self, orchestrator: Any) -> None:
        self._executor._orch = orchestrator

    def wire_tool_registry(self, tool_registry: Any) -> None:
        self._executor._tools = tool_registry


# Module-level singleton
_manager: SkillManager | None = None


def get_skill_manager() -> SkillManager:
    global _manager
    if _manager is None:
        _manager = SkillManager()
        _manager.load()
    return _manager
