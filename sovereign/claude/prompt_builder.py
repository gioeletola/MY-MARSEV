"""
Prompt builder for the SOVEREIGN AI OS.

Constructs CachedSystemPrompt objects by combining:
  - Static section: constitutional kernel + agent persona (→ cache_control: ephemeral)
  - Dynamic section: session context + memory snapshot (changes per request)

The static section must be identical across calls for the same agent type to
reliably hit Claude's prompt cache. Keep it deterministic and free of session state.
"""
from __future__ import annotations

from typing import Any

from sovereign.claude.client import CachedSystemPrompt
from sovereign.kernel.constitution import Constitution


class PromptBuilder:
    """
    Builds CachedSystemPrompt objects for any agent type.

    Usage:
        builder = PromptBuilder(constitution, prompt_registry)
        cached = builder.build_for_agent("ceo", task_context, memory_snapshot)
        response = await claude_client.complete(messages, system=cached)
    """

    def __init__(
        self,
        constitution: Constitution,
        prompt_registry: Any,  # sovereign.registries.PromptRegistry (avoid circular import)
    ) -> None:
        self._constitution = constitution
        self._registry = prompt_registry
        # Cache the constitutional prefix so it's computed once
        self._constitutional_prefix: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_for_agent(
        self,
        agent_id: str,
        task_context: dict[str, Any] | None = None,
        memory_snapshot: dict[str, Any] | None = None,
    ) -> CachedSystemPrompt:
        """
        Assemble a CachedSystemPrompt for the given agent.

        static_section = constitutional prefix + agent persona (from PromptRegistry)
        dynamic_section = session variables, task context, memory snapshot
        """
        static = self._build_static(agent_id)
        dynamic = self._build_dynamic(task_context or {}, memory_snapshot or {})
        return CachedSystemPrompt(static_section=static, dynamic_section=dynamic)

    def build_minimal(
        self,
        task_description: str,
        memory_snapshot: dict[str, Any] | None = None,
    ) -> CachedSystemPrompt:
        """
        Build a minimal cached prompt (constitutional prefix only, no agent persona).
        Used for ephemeral agents that don't have a registered persona.
        """
        static = self._build_constitutional_prefix()
        dynamic_parts = [f"## Current Task\n{task_description}"]
        if memory_snapshot:
            dynamic_parts.append(self._format_memory(memory_snapshot))
        return CachedSystemPrompt(
            static_section=static,
            dynamic_section="\n\n".join(dynamic_parts),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_static(self, agent_id: str) -> str:
        """Combine constitutional prefix with agent-specific persona."""
        prefix = self._build_constitutional_prefix()
        try:
            persona = self._registry.get(f"system/{agent_id}")
        except (KeyError, FileNotFoundError):
            persona = f"## Agent: {agent_id.upper()}\n\nYou are the {agent_id} agent."
        return f"{prefix}\n\n{persona}"

    def _build_constitutional_prefix(self) -> str:
        """
        Render the constitutional kernel as the cacheable prefix.
        Result is memoised — identical content on every call, maximising cache hits.
        """
        if self._constitutional_prefix is None:
            self._constitutional_prefix = self._constitution.render_for_prompt()
        return self._constitutional_prefix

    def _build_dynamic(
        self,
        task_context: dict[str, Any],
        memory_snapshot: dict[str, Any],
    ) -> str:
        """Build the dynamic (non-cached) section of the system prompt."""
        parts: list[str] = []

        if task_context:
            parts.append("## Session Context\n")
            for key, value in task_context.items():
                parts.append(f"  {key}: {value}")

        if memory_snapshot:
            parts.append(self._format_memory(memory_snapshot))

        return "\n".join(parts) if parts else ""

    @staticmethod
    def _format_memory(snapshot: dict[str, Any]) -> str:
        """Format a memory snapshot for injection into the dynamic section."""
        lines = ["## Relevant Memory\n"]
        for domain, records in snapshot.items():
            lines.append(f"### {domain.capitalize()}")
            if isinstance(records, dict):
                for k, v in records.items():
                    lines.append(f"  {k}: {v}")
            elif isinstance(records, list):
                for item in records:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"  {records}")
        return "\n".join(lines)
