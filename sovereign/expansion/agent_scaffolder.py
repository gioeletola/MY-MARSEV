"""Agent scaffolder — generates new agent code stubs from a spec."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AgentBlueprint:
    agent_id: str
    specialty: str
    instructions: str
    tools: list[str] = field(default_factory=list)
    model: str = "claude-sonnet-4-6"
    requires_review: bool = False
    confidence: float = 0.75
    domain: str = "general"


_TEMPLATE = '''\
"""Auto-generated agent: {specialty}."""
from sovereign.swarm.base_agent import BaseAgent
from sovereign.output.output_contract import StructuredOutput


class {class_name}(BaseAgent):
    agent_id = "{agent_id}"
    model = "{model}"
    requires_human_review = {requires_review}
    default_confidence = {confidence}

    SYSTEM_PROMPT = """You are {specialty}. {instructions}"""

    async def run(self, task, ctx):
        try:
            result = await self._call_claude(task, ctx, self.SYSTEM_PROMPT)
            return StructuredOutput.success(
                session_id=ctx.session_id,
                agent_id=self.agent_id,
                task_id=task.task_id,
                result=result.get("output", ""),
                confidence=self.default_confidence,
                requires_human_review=self.requires_human_review,
            )
        except Exception as exc:
            return StructuredOutput.failure(ctx.session_id, self.agent_id, task.task_id, str(exc))
'''


class AgentScaffolder:
    def __init__(self, output_dir: str = "sovereign/swarm/generated") -> None:
        self._output_dir = output_dir
        import pathlib
        pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)

    def generate_code(self, blueprint: AgentBlueprint) -> str:
        class_name = "".join(w.capitalize() for w in blueprint.specialty.split()) + "Agent"
        return _TEMPLATE.format(
            specialty=blueprint.specialty,
            class_name=class_name,
            agent_id=blueprint.agent_id,
            model=blueprint.model,
            requires_review=blueprint.requires_review,
            confidence=blueprint.confidence,
            instructions=blueprint.instructions,
        )

    def scaffold(self, blueprint: AgentBlueprint, write: bool = True) -> str:
        code = self.generate_code(blueprint)
        if write:
            import pathlib
            file_name = blueprint.agent_id.replace("-", "_") + ".py"
            path = pathlib.Path(self._output_dir) / file_name
            path.write_text(code)
            logger.info("Scaffolded agent: %s → %s", blueprint.agent_id, path)
        return code

    def scaffold_many(self, blueprints: list[AgentBlueprint]) -> list[str]:
        return [self.scaffold(bp) for bp in blueprints]
