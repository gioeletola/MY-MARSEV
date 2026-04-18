"""
Workflow registry — stores named multi-step workflow definitions and executes them.

A workflow is a sequence of agent steps where each step's output can be
passed as context to the next step.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sovereign.swarm.base_agent import AgentContext

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """A single step within a workflow."""
    agent_id: str
    objective_template: str     # May contain {variable} placeholders + {prev_result}
    tools_allowed: list[str] = field(default_factory=list)
    action_class: str = "SUGGEST"
    pass_previous_result: bool = True   # Inject previous step's result into context


@dataclass
class WorkflowDefinition:
    """A named, versioned sequence of agent steps."""
    name: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)


@dataclass
class WorkflowResult:
    """Aggregated result of a workflow execution."""
    workflow_name: str
    steps_completed: int
    steps_total: int
    outputs: list[dict[str, Any]] = field(default_factory=list)
    final_result: str = ""
    success: bool = True
    errors: list[str] = field(default_factory=list)


class WorkflowRegistry:
    """Stores, retrieves, and executes named workflow definitions."""

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}

    def register(self, workflow: WorkflowDefinition) -> None:
        self._workflows[workflow.name] = workflow

    def get(self, name: str) -> WorkflowDefinition:
        try:
            return self._workflows[name]
        except KeyError:
            raise KeyError(f"Workflow '{name}' not found.")

    def list_workflows(self) -> list[str]:
        return list(self._workflows)

    async def execute(
        self,
        name: str,
        variables: dict[str, Any],
        agent_resolver: Any,     # Callable[[str], BaseAgent]
        ctx: "AgentContext",
    ) -> WorkflowResult:
        """
        Execute a named workflow by running each step in sequence.

        Args:
            name:            Workflow name to execute.
            variables:       Variables to substitute in objective_template strings.
            agent_resolver:  Callable that takes an agent_id and returns the agent instance.
            ctx:             Shared AgentContext for all steps.

        Returns:
            WorkflowResult with per-step outputs and aggregated final_result.
        """
        from sovereign.swarm.base_agent import AgentTask
        from sovereign.kernel.action_classes import ActionClass

        workflow = self.get(name)
        result = WorkflowResult(
            workflow_name=name,
            steps_completed=0,
            steps_total=len(workflow.steps),
        )
        prev_result = ""

        for i, step in enumerate(workflow.steps):
            # Render objective template
            render_vars = {**variables, "prev_result": prev_result, "step": i + 1}
            try:
                objective = step.objective_template.format(**render_vars)
            except KeyError as exc:
                objective = step.objective_template   # Use as-is if template fails
                logger.warning("Workflow step template missing variable: %s", exc)

            # Inject previous result into context if requested
            step_context: dict[str, Any] = {
                "workflow": name,
                "step_index": i,
                "agent_hint": step.agent_id,
            }
            if step.pass_previous_result and prev_result:
                step_context["prev_result"] = prev_result[:2000]   # Cap injection size

            task = AgentTask(
                objective=objective,
                action_class=ActionClass.from_str(step.action_class),
                tools_allowed=step.tools_allowed,
                context=step_context,
            )

            try:
                agent = agent_resolver(step.agent_id)
                logger.info(
                    "Workflow step %d/%d: agent=%s", i + 1, len(workflow.steps), step.agent_id
                )
                output = await agent.run(task, ctx)
                prev_result = output.result or ""
                result.outputs.append({
                    "step": i + 1,
                    "agent_id": step.agent_id,
                    "status": output.status.value,
                    "result_preview": prev_result[:200],
                })
                result.steps_completed += 1
            except Exception as exc:
                error_msg = f"Step {i + 1} ({step.agent_id}) failed: {exc}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                result.success = False
                # Continue to next step unless it's the last one
                if i == len(workflow.steps) - 1:
                    break

        result.final_result = prev_result
        if result.errors:
            result.success = result.steps_completed > 0
        return result
