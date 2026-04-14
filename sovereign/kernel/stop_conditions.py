"""
Global stop condition evaluator for agent execution loops.

Checked at the top of every agent iteration to decide whether the loop
should be halted before the next Claude API call.
"""
from __future__ import annotations

from dataclasses import dataclass

from sovereign.kernel.constitution import Constitution


@dataclass
class StopConditionEvaluator:
    """
    Evaluates whether a running agent loop should be halted.

    Checks:
    - Iteration count against max_iterations
    - Cumulative token usage against session budget
    - Consecutive error count against error budget
    - Constitutional stop keywords in the latest agent output
    """

    constitution: Constitution
    max_iterations: int = 20
    max_tokens_per_session: int = 200_000
    error_budget: int = 3

    def should_stop(
        self,
        iteration: int,
        tokens_used: int,
        errors: int,
        agent_output: str = "",
    ) -> tuple[bool, str]:
        """
        Evaluate all stop conditions.

        Returns:
            (should_stop: bool, reason: str) — reason is empty string if not stopping.
        """
        if iteration >= self.max_iterations:
            return True, f"Max iterations reached ({self.max_iterations})"

        if tokens_used >= self.max_tokens_per_session:
            return True, (
                f"Token budget exhausted "
                f"({tokens_used} >= {self.max_tokens_per_session})"
            )

        if errors >= self.error_budget:
            return True, f"Error budget exhausted ({errors} consecutive errors)"

        if agent_output and self._check_keywords(agent_output):
            return True, "Constitutional stop keyword detected in agent output"

        return False, ""

    def _check_keywords(self, text: str) -> bool:
        """Return True if any constitutional stop keyword appears in the text."""
        return self.constitution.contains_stop_keyword(text)


@dataclass
class IterationState:
    """Mutable state tracked across one agent's execution loop."""

    iteration: int = 0
    tokens_used: int = 0
    errors: int = 0
    last_output: str = ""

    def tick(self) -> None:
        """Advance to the next iteration."""
        self.iteration += 1

    def record_error(self) -> None:
        """Increment error counter."""
        self.errors += 1

    def reset_errors(self) -> None:
        """Reset error counter on successful iteration."""
        self.errors = 0

    def add_tokens(self, n: int) -> None:
        """Accumulate token usage."""
        self.tokens_used += n
