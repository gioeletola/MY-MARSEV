"""
Skill executor — runs a SkillDefinition against the orchestrator/tool registry.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from sovereign.skills.security import check_execution_allowed, validate_skill
from sovereign.skills.types import SkillDefinition, SkillExecutionResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SkillExecutor:
    """
    Executes skills by resolving their prompt template against an orchestrator
    or by calling tool_registry directly for simple tool-backed skills.
    """

    def __init__(self, orchestrator: Any = None, tool_registry: Any = None) -> None:
        self._orch = orchestrator
        self._tools = tool_registry

    async def execute(
        self,
        skill: SkillDefinition,
        inputs: dict[str, Any],
        session_id: str = "skill",
    ) -> SkillExecutionResult:
        t0 = time.monotonic()

        # Security checks
        try:
            validate_skill(skill)
        except Exception as exc:
            return SkillExecutionResult(skill_id=skill.skill_id, success=False, error=str(exc))

        if not check_execution_allowed(skill):
            return SkillExecutionResult(
                skill_id=skill.skill_id, success=False,
                error=f"Skill {skill.skill_id!r} is disabled or not allowed",
            )

        # Validate required inputs
        for inp in skill.inputs:
            if inp.required and inp.name not in inputs and inp.default is None:
                return SkillExecutionResult(
                    skill_id=skill.skill_id, success=False,
                    error=f"Missing required input: {inp.name!r}",
                )

        # Build filled inputs (apply defaults)
        filled: dict[str, Any] = {}
        for inp in skill.inputs:
            filled[inp.name] = inputs.get(inp.name, inp.default)

        try:
            output = await self._run_skill(skill, filled, session_id)
            duration = (time.monotonic() - t0) * 1000
            return SkillExecutionResult(
                skill_id=skill.skill_id,
                success=True,
                output=output,
                duration_ms=duration,
                requires_human_review=skill.requires_approval,
            )
        except Exception as exc:
            logger.error("SkillExecutor: skill %s failed: %s", skill.skill_id, exc)
            return SkillExecutionResult(
                skill_id=skill.skill_id, success=False, error=str(exc),
                duration_ms=(time.monotonic() - t0) * 1000,
            )

    async def _run_skill(
        self,
        skill: SkillDefinition,
        inputs: dict[str, Any],
        session_id: str,
    ) -> dict[str, Any]:
        """Execute the skill via orchestrator or direct tool invocation."""
        if self._orch is not None and skill.prompt_template:
            prompt = skill.prompt_template
            for k, v in inputs.items():
                prompt = prompt.replace("{{" + k + "}}", str(v) if v is not None else "")
            result = await self._orch.handle_request(
                prompt, operating_mode=None, user_id=session_id
            )
            if hasattr(result, "result"):
                return {"result": result.result, "status": str(result.status)}
            return {"result": str(result)}

        # Fallback: try tool registry for single-tool skills
        if self._tools is not None and len(skill.tools) == 1:
            tool_id = skill.tools[0]
            try:
                return await self._tools.execute(tool_id, inputs, context={})
            except Exception as exc:
                raise RuntimeError(f"Tool {tool_id!r} execution failed: {exc}") from exc

        # Stub execution when no runtime is wired
        logger.warning("SkillExecutor: no runtime for skill %s — returning stub", skill.skill_id)
        return {"result": f"[Skill {skill.skill_id} executed (stub mode)]", "inputs": inputs}
