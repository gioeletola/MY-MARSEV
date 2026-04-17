"""
Claude API client for the SOVEREIGN AI OS.

Wraps the Anthropic AsyncAnthropic SDK with:
  - Prompt caching (cache_control: ephemeral on static system prompt blocks)
  - Tool use loop management (auto-cycles tool_use → tool_result rounds)
  - Streaming support
  - Exponential-backoff retry via tenacity
  - Cumulative token usage tracking (including cache_read_input_tokens)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Awaitable

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt caching helper
# ---------------------------------------------------------------------------


@dataclass
class CachedSystemPrompt:
    """
    A two-part system prompt designed to maximise Claude's prompt cache hits.

    static_section:  constitutional kernel + agent persona.
                     Must be identical across requests for the same agent type.
                     Marked with cache_control: ephemeral → cached after first call.
                     Should be >1024 tokens to meet cache eligibility.

    dynamic_section: session context, memory snapshot, current task.
                     Changes per request → no cache_control.
    """

    static_section: str
    dynamic_section: str = ""

    def to_api_blocks(self) -> list[dict[str, Any]]:
        """
        Convert to the Anthropic API ``system`` parameter format.

        Returns a list of content blocks:
          [
            {"type": "text", "text": <static>, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": <dynamic>}   # omitted if empty
          ]
        """
        blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self.static_section,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if self.dynamic_section:
            blocks.append({"type": "text", "text": self.dynamic_section})
        return blocks


# ---------------------------------------------------------------------------
# Token usage tracker
# ---------------------------------------------------------------------------


@dataclass
class TokenUsage:
    """Cumulative token usage for a Claude client session."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def update(self, usage: anthropic.types.Usage) -> None:
        """Accumulate counts from an API response usage object."""
        self.input_tokens += getattr(usage, "input_tokens", 0)
        self.output_tokens += getattr(usage, "output_tokens", 0)
        self.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0)
        self.cache_creation_input_tokens += getattr(
            usage, "cache_creation_input_tokens", 0
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "input": self.input_tokens,
            "output": self.output_tokens,
            "cache_read": self.cache_read_input_tokens,
            "cache_write": self.cache_creation_input_tokens,
        }

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def effective_input(self) -> int:
        """Billed input = input - cache_read (cache reads cost less)."""
        return self.input_tokens - self.cache_read_input_tokens


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------


# Retry on transient API errors only
_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
)


class ClaudeClient:
    """
    Sovereign's async interface to the Anthropic Claude API.

    One shared instance is injected into all agents, enabling:
      - Connection pool reuse
      - Shared cumulative token accounting
      - Centralised retry and error handling
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-sonnet-4-6",
        budget_enforcer: Any | None = None,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self.default_model = default_model
        self.usage = TokenUsage()
        self._budget = budget_enforcer

    # ------------------------------------------------------------------
    # Core completion
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[dict[str, Any]],
        system: CachedSystemPrompt | None = None,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
    ) -> anthropic.types.Message:
        """
        Single non-streaming completion.

        Args:
            messages:   Conversation history in Anthropic format.
            system:     Optional CachedSystemPrompt. Uses cache_control on static block.
            model:      Override default model.
            tools:      Optional list of tool schemas (Anthropic API format).
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0–1 for most models).

        Returns:
            Full anthropic.types.Message object.
        """
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system is not None:
            kwargs["system"] = system.to_api_blocks()
        if tools:
            kwargs["tools"] = tools

        # Token budget pre-check
        if self._budget is not None:
            try:
                self._budget.check(estimated_tokens=1000)
            except Exception as budget_exc:
                logger.warning("Token budget enforcer blocked call: %s", budget_exc)
                raise

        response: anthropic.types.Message = await self._client.messages.create(**kwargs)
        self.usage.update(response.usage)

        # Record spend
        if self._budget is not None:
            try:
                self._budget.record(
                    agent_id="claude_client",
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
            except Exception:
                pass

        logger.debug(
            "Claude API call complete",
            model=kwargs["model"],
            usage=response.usage,
        )
        return response

    # ------------------------------------------------------------------
    # Tool use loop
    # ------------------------------------------------------------------

    async def complete_with_tool_loop(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[Any]],
        system: CachedSystemPrompt | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        max_tool_rounds: int = 10,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Run the full tool_use agentic loop until stop_reason == "end_turn".

        Loop:
          1. Call Claude with tools list
          2. If stop_reason == "tool_use": execute each tool_use block,
             append tool_result blocks, continue
          3. If stop_reason == "end_turn": return final text + full history

        Args:
            messages:       Initial conversation history.
            tools:          Tool schemas in Anthropic API format.
            tool_executor:  Async callable(tool_name, tool_input) → result.
                            Provided by the agent's tool router.
            system:         Optional cached system prompt.
            model:          Optional model override.
            max_tokens:     Max tokens per API call.
            max_tool_rounds: Safety limit on tool rounds to prevent infinite loops.

        Returns:
            (final_text: str, full_messages: list[dict])
        """
        current_messages = list(messages)
        rounds = 0

        while rounds < max_tool_rounds:
            response = await self.complete(
                messages=current_messages,
                system=system,
                model=model,
                tools=tools,
                max_tokens=max_tokens,
            )

            # Append assistant turn to history
            current_messages.append(
                {"role": "assistant", "content": response.content}
            )

            if response.stop_reason == "end_turn":
                # Extract final text from the last assistant message
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text
                return final_text, current_messages

            if response.stop_reason == "tool_use":
                # Execute all tool_use blocks, collect tool_result blocks
                tool_results: list[dict[str, Any]] = []
                for block in response.content:
                    if block.type == "tool_use":
                        try:
                            result = await tool_executor(block.name, block.input)
                        except Exception as exc:
                            result = {"error": str(exc)}
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(result),
                            }
                        )

                current_messages.append(
                    {"role": "user", "content": tool_results}
                )
                rounds += 1
                continue

            # Unexpected stop_reason — return what we have
            logger.warning(
                "Unexpected stop_reason",
                stop_reason=response.stop_reason,
            )
            break

        # Fell through max_tool_rounds or unexpected stop
        final_text = ""
        for block in (response.content if "response" in dir() else []):  # type: ignore[possibly-undefined]
            if hasattr(block, "text"):
                final_text += block.text
        return final_text, current_messages

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream(
        self,
        messages: list[dict[str, Any]],
        system: CachedSystemPrompt | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """
        Async generator yielding text delta chunks as they arrive.

        Usage:
            async for chunk in client.stream(messages, system=prompt):
                print(chunk, end="", flush=True)
        """
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system is not None:
            kwargs["system"] = system.to_api_blocks()

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
            # Accumulate final usage after stream closes
            final_message = await stream.get_final_message()
            self.usage.update(final_message.usage)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def get_usage(self) -> dict[str, int]:
        """Return cumulative token usage as a plain dict."""
        return self.usage.to_dict()

    def reset_usage(self) -> None:
        """Reset cumulative token counters (call at session boundary if desired)."""
        self.usage = TokenUsage()
