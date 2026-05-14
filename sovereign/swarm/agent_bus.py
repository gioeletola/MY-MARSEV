"""Agent-to-agent direct communication bus."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

_AgentHandler = Callable[[str, dict], Coroutine[Any, Any, Any]]


class AgentBus:
    """In-process pub/sub bus for agent-to-agent messaging.

    Agents register themselves with a handler coroutine. Any agent can then
    call ``ask_agent(target_id, question)`` to send a direct message and
    await the response within a timeout.

    Usage::

        bus = AgentBus()
        bus.register("research", research_agent.handle_message)
        response = await bus.ask_agent("research", "Summarise Apple Q4 results")
    """

    def __init__(self) -> None:
        self._handlers: dict[str, _AgentHandler] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, agent_id: str, handler: _AgentHandler) -> None:
        """Register an agent's message handler."""
        self._handlers[agent_id] = handler
        logger.debug("AgentBus: registered '%s'", agent_id)

    def unregister(self, agent_id: str) -> None:
        self._handlers.pop(agent_id, None)

    def registered_agents(self) -> list[str]:
        return list(self._handlers.keys())

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def ask(
        self,
        sender_id: str,
        target_id: str,
        question: str,
        payload: dict | None = None,
        timeout: float = 30.0,
    ) -> Any:
        """Send a question to target_id and return its response.

        Raises RuntimeError if the target is not registered.
        Raises asyncio.TimeoutError if the target doesn't respond in time.
        """
        handler = self._handlers.get(target_id)
        if not handler:
            raise RuntimeError(
                f"AgentBus: no handler for '{target_id}'. "
                f"Available: {self.registered_agents()}"
            )
        envelope = {
            "message_id": str(uuid.uuid4())[:8],
            "sender": sender_id,
            "question": question,
            "payload": payload or {},
            "sent_at": time.time(),
        }
        logger.debug("AgentBus: %s → %s: %s", sender_id, target_id, question[:80])
        return await asyncio.wait_for(handler(question, envelope), timeout=timeout)

    async def broadcast(
        self,
        sender_id: str,
        question: str,
        payload: dict | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Send a question to all registered agents and collect responses.

        Returns ``{agent_id: response_or_error_dict}``.
        """
        tasks = {
            agent_id: asyncio.create_task(
                self.ask(sender_id, agent_id, question, payload, timeout)
            )
            for agent_id in self._handlers
            if agent_id != sender_id
        }
        results: dict[str, Any] = {}
        for agent_id, task in tasks.items():
            try:
                results[agent_id] = await task
            except Exception as exc:
                results[agent_id] = {"error": str(exc)}
        return results

    # ------------------------------------------------------------------
    # Convenience alias
    # ------------------------------------------------------------------

    async def ask_agent(
        self,
        target_id: str,
        question: str,
        sender_id: str = "anonymous",
        timeout: float = 30.0,
    ) -> Any:
        """Shorthand for ask() without an explicit payload."""
        return await self.ask(sender_id, target_id, question, timeout=timeout)
