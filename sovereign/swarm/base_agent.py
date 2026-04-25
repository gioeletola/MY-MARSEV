"""
Base agent contract for the SOVEREIGN AI OS swarm.

Defines:
  - AgentProtocol  — structural protocol every agent must satisfy
  - AgentTask      — unit of work dispatched to an agent
  - AgentContext   — runtime context injected per task
  - BaseAgent      — abstract base class with shared lifecycle, Claude API access,
                     tool dispatch, and logging
"""
from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from sovereign.kernel.action_classes import ActionClass
from sovereign.output.output_contract import OutputStatus, StructuredOutput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------


@dataclass
class AgentTask:
    """
    A unit of work dispatched to an agent.

    task_id:          Unique identifier (auto-generated if not provided).
    objective:        Natural-language description of what to accomplish.
    context:          Arbitrary key-value context for the agent.
    action_class:     Maximum allowed action class for this task.
    tools_allowed:    Names of tools the agent may call. Empty = no tools.
    parent_task_id:   ID of the parent task (for sub-task trees).
    max_iterations:   Hard cap on agent loop iterations.
    output_schema:    Optional JSON Schema the output data dict must conform to.
    """

    objective: str
    context: dict[str, Any] = field(default_factory=dict)
    action_class: ActionClass = ActionClass.SUGGEST
    tools_allowed: list[str] = field(default_factory=list)
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    parent_task_id: str | None = None
    max_iterations: int = 10
    output_schema: dict[str, Any] | None = None


@dataclass
class AgentContext:
    """
    Runtime context injected into an agent for a given session.

    Carries shared references so agents don't need to know about the
    broader orchestration topology.
    """

    session_id: str
    operating_mode: str
    memory_snapshot: dict[str, Any] = field(default_factory=dict)
    user_id: str = "default"
    constitution_hash: str = ""    # Used to verify prompt cache validity


# ---------------------------------------------------------------------------
# Protocol (structural typing)
# ---------------------------------------------------------------------------


@runtime_checkable
class AgentProtocol(Protocol):
    """
    Structural protocol every agent must satisfy.

    Checked at runtime with isinstance(obj, AgentProtocol).
    Agents do not need to inherit from this class — duck-typing is sufficient.
    """

    agent_id: str
    model: str

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput: ...

    def describe(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the swarm.

    Subclasses must:
      1. Define class-level ``agent_id`` and ``model`` attributes.
      2. Implement ``run(task, ctx) -> StructuredOutput``.

    Provided for free:
      - _call_claude():        Calls Claude with the agent's cached system prompt.
      - _call_with_tools():    Runs the full tool-use loop.
      - _handle_tool_call():   Looks up and executes a tool from the registry.
      - _build_system_prompt(): Assembles the CachedSystemPrompt for this agent.
      - describe():            Returns a serialisable description for registries.
    """

    agent_id: str = "base"
    model: str = "claude-sonnet-4-6"
    superpower_packs: list[str] = []   # e.g. ["negotiation", "mental_models"]

    def __init__(
        self,
        claude_client: Any,       # ClaudeClient — avoid circular import with TYPE_CHECKING
        tool_registry: Any,       # ToolRegistry
        memory_manager: Any,      # MemoryManager
        constitution: Any,        # Constitution
        prompt_builder: Any,      # PromptBuilder
    ) -> None:
        self._claude = claude_client
        self._tools = tool_registry
        self._memory = memory_manager
        self._constitution = constitution
        self._prompt_builder = prompt_builder
        self._superpower_loader: Any = None
        if self.superpower_packs:
            try:
                from sovereign.superpower_files.loader import SuperpowerLoader
                self._superpower_loader = SuperpowerLoader()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        """
        Execute the agent's primary task loop.

        Must return a StructuredOutput regardless of success or failure.
        Never raise — catch exceptions and return StructuredOutput.failure().
        """
        ...

    # ------------------------------------------------------------------
    # Shared Claude API helpers
    # ------------------------------------------------------------------

    async def _call_claude(
        self,
        messages: list[dict[str, Any]],
        ctx: AgentContext,
        task: AgentTask | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """
        Call Claude with this agent's cached system prompt.

        Returns the text content of the response.
        """
        system = self._prompt_builder.build_for_agent(
            agent_id=self.agent_id,
            task_context={
                "operating_mode": ctx.operating_mode,
                "session_id": ctx.session_id,
                **({"objective": task.objective} if task else {}),
            },
            memory_snapshot=ctx.memory_snapshot,
        )
        response = await self._claude.complete(
            messages=messages,
            system=system,
            model=self.model,
            max_tokens=max_tokens,
        )
        # Extract text from response
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return text

    async def _call_with_tools(
        self,
        messages: list[dict[str, Any]],
        ctx: AgentContext,
        task: AgentTask,
        max_tokens: int = 4096,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Call Claude with tools and run the full tool-use loop.

        Only tools in task.tools_allowed are passed to the API.

        Returns:
            (final_text, full_message_history)
        """
        system = self._prompt_builder.build_for_agent(
            agent_id=self.agent_id,
            task_context={
                "operating_mode": ctx.operating_mode,
                "session_id": ctx.session_id,
                "objective": task.objective,
            },
            memory_snapshot=ctx.memory_snapshot,
        )
        tool_schemas = self._tools.list_schemas(allowed=task.tools_allowed)

        return await self._claude.complete_with_tool_loop(
            messages=messages,
            tools=tool_schemas,
            tool_executor=self._handle_tool_call,
            system=system,
            model=self.model,
            max_tokens=max_tokens,
        )

    async def _handle_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> Any:
        """
        Look up a tool in the registry by name and execute it.

        This is the callable passed to ClaudeClient.complete_with_tool_loop.
        """
        logger.debug("Executing tool", agent=self.agent_id, tool=tool_name)
        result = await self._tools.execute(tool_name, tool_input)
        return result

    # ------------------------------------------------------------------
    # System prompt helper
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        ctx: AgentContext,
        task: AgentTask | None = None,
    ) -> Any:  # CachedSystemPrompt
        """Build the cached system prompt for this agent's current context."""
        prompt = self._prompt_builder.build_for_agent(
            agent_id=self.agent_id,
            task_context={
                "operating_mode": ctx.operating_mode,
                **({"objective": task.objective} if task else {}),
            },
            memory_snapshot=ctx.memory_snapshot,
        )
        # Inject superpower knowledge packs if configured
        if self._superpower_loader and self.superpower_packs:
            try:
                extra = "\n\n".join(
                    self._superpower_loader.render(p)
                    for p in self.superpower_packs
                    if self._superpower_loader.get(p)
                )
                if extra and hasattr(prompt, "static_section"):
                    prompt.static_section += "\n\n" + extra
            except Exception:
                pass
        return prompt

    # ------------------------------------------------------------------
    # Registry / observability
    # ------------------------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """Return a serialisable description for registry and observability."""
        return {
            "agent_id": self.agent_id,
            "model": self.model,
            "class": type(self).__name__,
        }

    def _make_output(
        self,
        task: AgentTask,
        ctx: AgentContext,
        result: str,
        status: OutputStatus = OutputStatus.SUCCESS,
        data: dict[str, Any] | None = None,
        reasoning: str = "",
        confidence: float = 0.8,
    ) -> StructuredOutput:
        """Convenience factory for building a StructuredOutput from this agent."""
        return StructuredOutput(
            session_id=ctx.session_id,
            agent_id=self.agent_id,
            task_id=task.task_id,
            status=status,
            result=result,
            data=data or {},
            reasoning=reasoning,
            confidence=confidence,
            tokens_used=self._claude.get_usage(),
        )


# ---------------------------------------------------------------------------
# Worker factory — shared across all domain agent modules
# ---------------------------------------------------------------------------

def _make_worker(
    agent_id: str,
    specialty: str,
    instructions: str,
    tools: list[str] | None = None,
    model: str = "claude-sonnet-4-6",
    requires_review: bool = False,
    confidence: float = 0.82,
):
    """
    Build a concrete BaseAgent subclass from a plain descriptor.

    All swarm domain files (finance, business, personal, black_tier, …) import
    this function instead of defining their own local copy.
    """
    _tools = tools or ["memory_tool"]
    _model = model
    _review = requires_review
    _conf = confidence

    async def run(self, task: AgentTask, ctx: AgentContext) -> StructuredOutput:
        try:
            if not task.tools_allowed:
                task.tools_allowed = list(_tools)
            prompt = (
                f"You are the {specialty} of the SOVEREIGN AI OS.\n\n"
                f"{instructions}\n\n"
                f"Task:\n{task.objective}\n\n"
                "Be precise, structured, and actionable."
            )
            result, history = await self._call_with_tools(
                [{"role": "user", "content": prompt}], ctx, task, max_tokens=2048
            )
            out = self._make_output(
                task=task, ctx=ctx, result=result,
                status=OutputStatus.SUCCESS, confidence=_conf,
                data={"specialty": specialty, "tool_turns": len(history)},
            )
            out.requires_human_review = _review
            return out
        except Exception as exc:
            logger.error("Agent %s failed: %s", agent_id, exc)
            return StructuredOutput.failure(ctx.session_id, agent_id, task.task_id, str(exc))

    class_name = agent_id.replace("-", "_").title().replace("_", "") + "Agent"
    return type(class_name, (BaseAgent,), {"agent_id": agent_id, "model": _model, "run": run})
