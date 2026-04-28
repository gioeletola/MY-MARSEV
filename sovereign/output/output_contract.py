"""
Structured output contract for the SOVEREIGN AI OS.

Every agent in the swarm returns a StructuredOutput. This ensures
consistent shape, auditability, and downstream composability across
the entire multi-agent pipeline.

New in this version:
  - metadata, warnings, suggestions fields
  - to_markdown() / to_summary() methods
  - merge(*outputs) static method
  - OutputStatus enum (richer lifecycle states)
  - OutputFormatter class (markdown|json|table|slack)
"""
from __future__ import annotations

import datetime
import json
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OutputStatus(str, Enum):
    """Lifecycle status of an agent's task execution."""

    # New primary states
    PENDING         = "pending"
    RUNNING         = "running"
    COMPLETED       = "completed"
    FAILED          = "failed"
    PARTIAL         = "partial"
    REQUIRES_REVIEW = "requires_review"

    # Legacy aliases (kept for backward compatibility)
    SUCCESS         = "success"
    ESCALATED       = "escalated"
    PENDING_APPROVAL = "pending_approval"
    SKIPPED         = "skipped"

    @property
    def is_terminal(self) -> bool:
        return self in (
            OutputStatus.COMPLETED, OutputStatus.FAILED,
            OutputStatus.SUCCESS, OutputStatus.ESCALATED,
            OutputStatus.SKIPPED,
        )

    @property
    def is_ok(self) -> bool:
        return self in (OutputStatus.COMPLETED, OutputStatus.SUCCESS, OutputStatus.PARTIAL)


@dataclass
class StructuredOutput:
    """
    17-field standard output contract.

    Every agent in the swarm returns exactly this type.
    Fields are ordered by importance for human review.
    """

    # --- Identity & tracing ---
    session_id: str                                         # 1. Session identifier
    agent_id: str                                           # 2. Producing agent
    task_id: str                                            # 3. Task this output answers

    # --- Status ---
    status: OutputStatus                                    # 4. Lifecycle status

    # --- Primary payload ---
    result: str                                             # 5. Human-readable answer/output

    # --- Structured data ---
    data: dict[str, Any] = field(default_factory=dict)     # 6. Structured data payload

    # --- Reasoning & audit ---
    reasoning: str = ""                                     # 7. Internal reasoning trace
    actions_taken: list[dict[str, Any]] = field(           # 8. Side effects performed
        default_factory=list
    )

    # --- Downstream work ---
    sub_tasks: list[str] = field(default_factory=list)     # 9. Follow-up task IDs spawned
    memory_updates: list[dict[str, Any]] = field(          # 10. Memory writes triggered
        default_factory=list
    )

    # --- Quality & cost ---
    confidence: float = 0.0                                 # 11. 0.0–1.0
    tokens_used: dict[str, int] = field(                   # 12. Token breakdown
        default_factory=lambda: {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
        }
    )

    # --- Timestamps ---
    completed_at: str = field(                             # 13. ISO-8601 UTC timestamp
        default_factory=lambda: datetime.datetime.utcnow().isoformat() + "Z"
    )

    # --- Human review flag ---
    requires_human_review: bool = False                    # 14. Escalation trigger

    # --- NEW fields ---
    metadata: dict[str, Any] = field(default_factory=dict)     # 15. Arbitrary metadata
    warnings: list[str] = field(default_factory=list)          # 16. Non-fatal warnings
    suggestions: list[str] = field(default_factory=list)        # 17. From suggestion engine

    # --- Internal: error detail (not part of the public fields) ---
    error: str = ""

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (JSON-safe values only)."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "data": self.data,
            "reasoning": self.reasoning,
            "actions_taken": self.actions_taken,
            "sub_tasks": self.sub_tasks,
            "memory_updates": self.memory_updates,
            "confidence": self.confidence,
            "tokens_used": self.tokens_used,
            "completed_at": self.completed_at,
            "requires_human_review": self.requires_human_review,
            "metadata": self.metadata,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "error": self.error,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """
        Render output as a Markdown document.

        Suitable for Notion, GitHub, Telegram messages, and reports.
        """
        lines: list[str] = []
        status_icon = {
            "completed": "✅", "success": "✅", "failed": "❌",
            "partial": "⚠️", "requires_review": "🔍", "escalated": "🚨",
            "pending": "⏳", "running": "🔄", "pending_approval": "⏸️",
            "skipped": "⏭️",
        }.get(self.status.value, "•")

        lines.append(f"# {status_icon} Agent Output — `{self.agent_id}`")
        lines.append("")
        lines.append(f"**Status:** {self.status.value.upper()}  |  "
                     f"**Confidence:** {self.confidence:.0%}  |  "
                     f"**Task:** `{self.task_id}`")
        lines.append("")
        lines.append("## Result")
        lines.append(self.result)

        if self.warnings:
            lines.append("")
            lines.append("## ⚠️ Warnings")
            for w in self.warnings:
                lines.append(f"- {w}")

        if self.suggestions:
            lines.append("")
            lines.append("## 💡 Suggestions")
            for s in self.suggestions:
                lines.append(f"- {s}")

        if self.reasoning:
            lines.append("")
            lines.append("## Reasoning")
            lines.append(textwrap.indent(self.reasoning, "> ", predicate=lambda _: True))

        if self.actions_taken:
            lines.append("")
            lines.append("## Actions Taken")
            for action in self.actions_taken:
                name = action.get("name", action.get("tool", "action"))
                lines.append(f"- `{name}`")

        if self.data:
            lines.append("")
            lines.append("## Data")
            lines.append("```json")
            lines.append(json.dumps(self.data, indent=2, default=str))
            lines.append("```")

        if self.sub_tasks:
            lines.append("")
            lines.append("## Sub-tasks Spawned")
            for t in self.sub_tasks:
                lines.append(f"- `{t}`")

        tokens_total = sum(self.tokens_used.values())
        lines.append("")
        lines.append("---")
        lines.append(f"*Session `{self.session_id}` · Completed {self.completed_at} · {tokens_total} tokens*")

        if self.error:
            lines.append("")
            lines.append(f"**Error:** `{self.error}`")

        return "\n".join(lines)

    def to_summary(self) -> str:
        """
        Compact one-liner summary.

        Format: [STATUS] agent_id — result (confidence=X%)
        """
        result_short = self.result[:80].replace("\n", " ")
        if len(self.result) > 80:
            result_short += "…"
        warn_tag = f" [{len(self.warnings)} warnings]" if self.warnings else ""
        return (
            f"[{self.status.value.upper()}] {self.agent_id} — "
            f"{result_short} (conf={self.confidence:.0%}){warn_tag}"
        )

    # ------------------------------------------------------------------
    # Static / class methods
    # ------------------------------------------------------------------

    @staticmethod
    def merge(*outputs: StructuredOutput) -> StructuredOutput:
        """
        Merge multiple StructuredOutput objects into one.

        Rules:
          - Uses session_id / agent_id / task_id from the first output
          - Status: COMPLETED if all OK, PARTIAL if some failed, FAILED if all failed
          - result: concatenated results
          - data, metadata: deep-merged (later outputs win on conflicts)
          - reasoning, warnings, suggestions: concatenated
          - tokens_used: summed
          - confidence: weighted average by output count
          - requires_human_review: OR of all flags
        """
        if not outputs:
            raise ValueError("merge() requires at least one output")
        if len(outputs) == 1:
            return outputs[0]

        first = outputs[0]
        all_ok = all(o.status.is_ok for o in outputs)
        all_failed = all(o.status == OutputStatus.FAILED for o in outputs)

        if all_ok:
            merged_status = OutputStatus.COMPLETED
        elif all_failed:
            merged_status = OutputStatus.FAILED
        else:
            merged_status = OutputStatus.PARTIAL

        merged_data: dict = {}
        merged_meta: dict = {}
        for o in outputs:
            merged_data.update(o.data)
            merged_meta.update(o.metadata)

        merged_tokens: dict[str, int] = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        for o in outputs:
            for k in merged_tokens:
                merged_tokens[k] += o.tokens_used.get(k, 0)

        merged_confidence = sum(o.confidence for o in outputs) / len(outputs)
        merged_result = "\n\n".join(o.result for o in outputs if o.result)
        merged_reasoning = "\n\n---\n\n".join(o.reasoning for o in outputs if o.reasoning)
        merged_warnings = [w for o in outputs for w in o.warnings]
        merged_suggestions = [s for o in outputs for s in o.suggestions]
        merged_actions = [a for o in outputs for a in o.actions_taken]
        merged_subtasks = [t for o in outputs for t in o.sub_tasks]
        merged_memory = [m for o in outputs for m in o.memory_updates]
        merged_errors = "; ".join(o.error for o in outputs if o.error)
        merged_review = any(o.requires_human_review for o in outputs)

        return StructuredOutput(
            session_id=first.session_id,
            agent_id=f"merged({','.join(o.agent_id for o in outputs)})",
            task_id=first.task_id,
            status=merged_status,
            result=merged_result,
            data=merged_data,
            reasoning=merged_reasoning,
            actions_taken=merged_actions,
            sub_tasks=merged_subtasks,
            memory_updates=merged_memory,
            confidence=merged_confidence,
            tokens_used=merged_tokens,
            completed_at=datetime.datetime.utcnow().isoformat() + "Z",
            requires_human_review=merged_review,
            metadata=merged_meta,
            warnings=merged_warnings,
            suggestions=merged_suggestions,
            error=merged_errors,
        )

    def add_tokens(self, usage: dict[str, int]) -> None:
        """Accumulate token counts from a Claude API usage object."""
        for key in ("input", "output", "cache_read", "cache_write"):
            self.tokens_used[key] = self.tokens_used.get(key, 0) + usage.get(key, 0)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def failure(
        cls,
        session_id: str,
        agent_id: str,
        task_id: str,
        error: str,
        requires_human_review: bool = False,
    ) -> StructuredOutput:
        """Create a failure output with a minimal footprint."""
        return cls(
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            status=OutputStatus.FAILED,
            result=f"Task failed: {error}",
            error=error,
            requires_human_review=requires_human_review,
        )

    @classmethod
    def escalated(
        cls,
        session_id: str,
        agent_id: str,
        task_id: str,
        reason: str,
    ) -> StructuredOutput:
        """Create an output that signals escalation to human authority."""
        return cls(
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            status=OutputStatus.ESCALATED,
            result=f"Escalated to human authority: {reason}",
            requires_human_review=True,
        )

    @classmethod
    def pending(
        cls,
        session_id: str,
        agent_id: str,
        task_id: str,
        reason: str,
    ) -> StructuredOutput:
        """Create an output waiting for approval before proceeding."""
        return cls(
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            status=OutputStatus.PENDING_APPROVAL,
            result=f"Awaiting approval: {reason}",
            requires_human_review=True,
        )

    @classmethod
    def ok(
        cls,
        session_id: str,
        agent_id: str,
        task_id: str,
        result: str,
        data: dict | None = None,
        confidence: float = 0.85,
        suggestions: list[str] | None = None,
    ) -> StructuredOutput:
        """Shorthand for a successful, completed output."""
        return cls(
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            status=OutputStatus.COMPLETED,
            result=result,
            data=data or {},
            confidence=confidence,
            suggestions=suggestions or [],
        )


# ---------------------------------------------------------------------------
# OutputFormatter
# ---------------------------------------------------------------------------

class OutputFormatter:
    """
    Format a StructuredOutput in multiple presentation formats.

    Formats:
      markdown — rich Markdown document
      json     — pretty-printed JSON
      table    — ASCII table for terminal output
      slack    — Slack Block Kit mrkdwn-compatible text
    """

    def format(
        self,
        output: StructuredOutput,
        fmt: str = "markdown",
    ) -> str:
        """
        Format *output* as the specified format string.

        Args:
            output – the StructuredOutput to format
            fmt    – "markdown" | "json" | "table" | "slack"

        Returns:
            Formatted string representation.
        """
        fmt = fmt.lower()
        if fmt == "markdown":
            return output.to_markdown()
        if fmt == "json":
            return output.to_json(indent=2)
        if fmt == "table":
            return self._format_table(output)
        if fmt == "slack":
            return self._format_slack(output)
        raise ValueError(f"Unknown format {fmt!r}. Valid: markdown|json|table|slack")

    def _format_table(self, output: StructuredOutput) -> str:
        """ASCII table suitable for terminal display."""
        rows = [
            ("Field", "Value"),
            ("─" * 20, "─" * 55),
            ("Agent",     output.agent_id),
            ("Task ID",   output.task_id),
            ("Status",    output.status.value.upper()),
            ("Confidence", f"{output.confidence:.0%}"),
            ("Result",    textwrap.shorten(output.result, 55, placeholder="…")),
        ]
        if output.warnings:
            rows.append(("Warnings", f"{len(output.warnings)} warning(s)"))
        if output.suggestions:
            rows.append(("Suggestions", f"{len(output.suggestions)} suggestion(s)"))
        if output.error:
            rows.append(("Error", textwrap.shorten(output.error, 55, placeholder="…")))
        rows.append(("Completed At", output.completed_at))
        tokens = sum(output.tokens_used.values())
        rows.append(("Tokens", str(tokens)))

        col1_w = max(len(r[0]) for r in rows)
        lines = []
        for k, v in rows:
            lines.append(f"  {k:<{col1_w}}  {v}")
        return "\n".join(lines)

    def _format_slack(self, output: StructuredOutput) -> str:
        """Slack mrkdwn-compatible text."""
        status_emoji = {
            "completed": ":white_check_mark:", "success": ":white_check_mark:",
            "failed": ":x:", "partial": ":warning:", "requires_review": ":mag:",
            "escalated": ":rotating_light:", "pending": ":hourglass:",
            "running": ":arrows_counterclockwise:",
        }.get(output.status.value, ":information_source:")

        lines = [
            f"{status_emoji} *{output.agent_id}* — `{output.status.value.upper()}`",
            f"*Task:* `{output.task_id}` | *Confidence:* {output.confidence:.0%}",
            "",
            f"*Result:* {output.result[:500]}",
        ]
        if output.warnings:
            lines.append(f":warning: *Warnings:* {'; '.join(output.warnings[:3])}")
        if output.suggestions:
            lines.append(f":bulb: *Suggestions:* {'; '.join(output.suggestions[:3])}")
        if output.error:
            lines.append(f":x: *Error:* `{output.error[:200]}`")
        lines.append(f"_Session `{output.session_id}` · {output.completed_at}_")
        return "\n".join(lines)

    def format_many(
        self,
        outputs: list[StructuredOutput],
        fmt: str = "markdown",
    ) -> str:
        """Format multiple outputs, separated by dividers."""
        sep = "\n\n---\n\n" if fmt == "markdown" else "\n\n"
        return sep.join(self.format(o, fmt) for o in outputs)
