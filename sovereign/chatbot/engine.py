"""ConversationEngine — multi-turn Claude-backed chatbot with intent routing."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, AsyncIterator

from .types import ChatResponse, ChatSession, MessageRole

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are SOVEREIGN — an intelligent AI operating system assistant. You are helpful, direct, and precise. You can assist with:
- Strategy, planning, and decision making
- Research and analysis
- Code, systems, and technical tasks
- Finance, business, and personal productivity
- Creative writing and communication
- General knowledge and reasoning

Be concise. When uncertain, say so. Never make up facts. Format answers in Markdown when it helps clarity."""


class ConversationEngine:
    """
    Multi-turn conversation engine backed by the Claude API (or stub).
    Supports streaming, intent detection, and session management.
    """

    def __init__(
        self,
        claude_client: Any = None,
        model: str = "",
        max_context_messages: int = 40,
        system_prompt: str = _SYSTEM_PROMPT,
    ) -> None:
        self._client = claude_client
        self._model = model or os.environ.get("SOVEREIGN_CHAT_MODEL", "claude-sonnet-4-6")
        self._max_ctx = max_context_messages
        self._system = system_prompt
        self._intent_radar: Any = None
        try:
            from sovereign.perception.intent_radar import IntentRadar
            self._intent_radar = IntentRadar()
        except Exception:
            pass

    def set_claude_client(self, client: Any) -> None:
        self._client = client

    async def chat(
        self,
        session: ChatSession,
        user_message: str,
        stream: bool = False,
    ) -> ChatResponse:
        t0 = time.monotonic()
        intent = ""
        mode_hint = ""
        if self._intent_radar:
            try:
                detected = self._intent_radar.classify(user_message)
                if detected:
                    intent = detected.intent
                    mode_hint = detected.mode_hint
            except Exception:
                pass

        session.add_message(MessageRole.USER, user_message)
        ctx_messages = session.last_n(self._max_ctx)
        api_messages = [m.to_api_dict() for m in ctx_messages if m.role != MessageRole.SYSTEM]

        try:
            content, tokens_in, tokens_out, tokens_cache = await self._call_claude(api_messages)
        except Exception as exc:
            logger.error("ConversationEngine: claude call failed: %s", exc)
            content = f"[Error: {exc}]"
            tokens_in = tokens_out = tokens_cache = 0

        msg = session.add_message(MessageRole.ASSISTANT, content)
        session.token_count += tokens_in + tokens_out
        latency = (time.monotonic() - t0) * 1000

        return ChatResponse(
            content=content,
            session_id=session.session_id,
            message_id=msg.message_id,
            model=self._model,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            tokens_cache_read=tokens_cache,
            intent=intent,
            mode_hint=mode_hint,
            latency_ms=latency,
        )

    async def stream_chat(
        self,
        session: ChatSession,
        user_message: str,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they stream from the model."""
        session.add_message(MessageRole.USER, user_message)
        ctx_messages = session.last_n(self._max_ctx)
        api_messages = [m.to_api_dict() for m in ctx_messages if m.role != MessageRole.SYSTEM]

        full_content = ""
        async for chunk in self._stream_claude(api_messages):
            full_content += chunk
            yield chunk

        session.add_message(MessageRole.ASSISTANT, full_content)

    async def _call_claude(self, messages: list[dict]) -> tuple[str, int, int, int]:
        """Returns (content, tokens_in, tokens_out, tokens_cache_read)."""
        if self._client is None:
            return self._stub_response(messages), 0, 0, 0

        try:
            import anthropic  # type: ignore
            client: anthropic.AsyncAnthropic = (
                self._client._client if hasattr(self._client, "_client") else self._client
            )
            response = await client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": self._system,
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
                messages=messages,
            )
            content = response.content[0].text if response.content else ""
            usage = response.usage
            return (
                content,
                getattr(usage, "input_tokens", 0),
                getattr(usage, "output_tokens", 0),
                getattr(usage, "cache_read_input_tokens", 0),
            )
        except Exception as exc:
            raise RuntimeError(f"Claude API error: {exc}") from exc

    async def _stream_claude(self, messages: list[dict]) -> AsyncIterator[str]:
        if self._client is None:
            for word in self._stub_response(messages).split():
                yield word + " "
            return

        try:
            client = self._client._client if hasattr(self._client, "_client") else self._client
            async with client.messages.stream(
                model=self._model,
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": self._system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as exc:
            yield f"\n[Stream error: {exc}]"

    def _stub_response(self, messages: list[dict]) -> str:
        last = messages[-1]["content"] if messages else ""
        return f"[SOVEREIGN Chatbot — stub mode] Received: {last[:120]!r}"
