"""
Agent Factory — creates, tracks, and destroys ephemeral sub-agents.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sovereign.factory.agent_spec import AgentSpec
from sovereign.swarm.ephemeral_agent import EphemeralAgent

logger = logging.getLogger(__name__)

MAX_CONCURRENT_EPHEMERAL = 10


# ── Agent Pool ────────────────────────────────────────────────────────────────

@dataclass
class _PoolEntry:
    agent: EphemeralAgent
    spawned_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    use_count: int = 0
    recycled: bool = False


class AgentPool:
    """LRU pool of reusable EphemeralAgent instances.

    Attributes:
        max_size: hard cap on pool entries.
        idle_timeout_seconds: entries unused longer than this are evicted.
    """

    def __init__(self, max_size: int = 20, idle_timeout_seconds: float = 300.0) -> None:
        self.max_size = max_size
        self.idle_timeout_seconds = idle_timeout_seconds
        self._entries: dict[str, _PoolEntry] = {}

    def add(self, agent: EphemeralAgent) -> None:
        self._evict_expired()
        if len(self._entries) >= self.max_size:
            self._evict_lru()
        self._entries[agent.agent_id] = _PoolEntry(agent=agent)

    def get(self, agent_id: str) -> EphemeralAgent | None:
        entry = self._entries.get(agent_id)
        if entry is None:
            return None
        entry.last_used_at = time.time()
        entry.use_count += 1
        return entry.agent

    def remove(self, agent_id: str) -> bool:
        return bool(self._entries.pop(agent_id, None))

    def all_agents(self) -> dict[str, EphemeralAgent]:
        return {aid: e.agent for aid, e in self._entries.items()}

    def stats(self) -> dict:
        now = time.time()
        entries = list(self._entries.values())
        if not entries:
            return {"size": 0, "avg_lifetime_s": 0.0, "avg_use_count": 0.0}
        avg_life = sum(now - e.spawned_at for e in entries) / len(entries)
        avg_use = sum(e.use_count for e in entries) / len(entries)
        return {
            "size": len(entries),
            "max_size": self.max_size,
            "avg_lifetime_s": round(avg_life, 1),
            "avg_use_count": round(avg_use, 2),
        }

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [
            aid for aid, e in self._entries.items()
            if now - e.last_used_at > self.idle_timeout_seconds
        ]
        for aid in expired:
            logger.debug("AgentPool: evicting idle agent %s", aid)
            del self._entries[aid]

    def _evict_lru(self) -> None:
        if not self._entries:
            return
        lru_id = min(self._entries, key=lambda aid: self._entries[aid].last_used_at)
        logger.debug("AgentPool: LRU eviction of agent %s", lru_id)
        del self._entries[lru_id]


# ── Agent Factory ─────────────────────────────────────────────────────────────

class AgentFactory:
    """
    Manages the lifecycle of ephemeral sub-agents.

    Enforces a concurrency limit (MAX_CONCURRENT_EPHEMERAL) to prevent
    unbounded resource consumption.
    """

    def __init__(
        self,
        claude_client: Any,
        tool_registry: Any,
        memory_manager: Any,
        constitution: Any,
        prompt_builder: Any,
        agent_registry: Any,
        pool: AgentPool | None = None,
    ) -> None:
        self._claude = claude_client
        self._tools = tool_registry
        self._memory = memory_manager
        self._constitution = constitution
        self._prompt_builder = prompt_builder
        self._agent_registry = agent_registry
        self._active: dict[str, EphemeralAgent] = {}
        self._pool: AgentPool = pool or AgentPool()
        # Usage frequency counter by agent type (spec.name)
        self._heat: dict[str, int] = defaultdict(int)
        # Spawn timestamps for lifetime tracking
        self._spawn_times: dict[str, float] = {}

    # ── Spawn / despawn ───────────────────────────────────────────────────

    async def spawn(self, spec: AgentSpec) -> EphemeralAgent:
        """Validate the spec, instantiate an EphemeralAgent, register it, and return it.

        Raises:
            ValueError: If spec is invalid or concurrency limit exceeded.
        """
        spec.validate()

        if len(self._active) >= MAX_CONCURRENT_EPHEMERAL:
            raise ValueError(
                f"Concurrency limit reached ({MAX_CONCURRENT_EPHEMERAL}). "
                "Despawn an agent before spawning a new one."
            )

        agent = EphemeralAgent(
            spec=spec,
            claude_client=self._claude,
            tool_registry=self._tools,
            memory_manager=self._memory,
            constitution=self._constitution,
            prompt_builder=self._prompt_builder,
        )
        self._active[agent.agent_id] = agent
        self._pool.add(agent)
        self._spawn_times[agent.agent_id] = time.time()
        self._heat[spec.name] += 1

        try:
            self._agent_registry.register(agent)
        except ValueError:
            pass  # Already registered (e.g., in tests)

        logger.info("AgentFactory: spawned %s (id=%s)", spec.name, agent.agent_id)
        return agent

    async def spawn_batch(self, specs: list[AgentSpec]) -> list[EphemeralAgent]:
        """Spawn multiple agents in parallel (respects concurrency limit)."""
        tasks = [self.spawn(spec) for spec in specs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        agents: list[EphemeralAgent] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error("AgentFactory.spawn_batch: spec[%d] failed — %s", i, r)
            else:
                agents.append(r)  # type: ignore[arg-type]
        return agents

    async def despawn(self, agent_id: str) -> bool:
        """Deregister and clean up an ephemeral agent. Returns True if found."""
        found = agent_id in self._active
        self._active.pop(agent_id, None)
        self._pool.remove(agent_id)
        self._spawn_times.pop(agent_id, None)
        try:
            self._agent_registry.deregister(agent_id)
        except Exception:
            pass
        logger.info("AgentFactory: despawned agent %s", agent_id)
        return found

    def recycle(self, agent_id: str) -> bool:
        """Reset agent state for reuse (clears conversation history if present)."""
        agent = self._active.get(agent_id)
        if agent is None:
            return False
        # Reset iteration counter and history if attributes exist
        for attr in ("_iteration", "_history", "_messages"):
            if hasattr(agent, attr):
                try:
                    default = 0 if attr == "_iteration" else []
                    setattr(agent, attr, default)
                except Exception:
                    pass
        entry = self._pool._entries.get(agent_id)
        if entry:
            entry.recycled = True
            entry.last_used_at = time.time()
        logger.debug("AgentFactory: recycled agent %s", agent_id)
        return True

    # ── Pool & stats ──────────────────────────────────────────────────────

    def get_pool(self) -> dict[str, EphemeralAgent]:
        """Return all currently active agents."""
        return dict(self._active)

    def pool_stats(self) -> dict:
        """Active count, average lifetime, and per-type breakdown."""
        now = time.time()
        active_ids = list(self._active.keys())
        lifetimes = [now - self._spawn_times[aid] for aid in active_ids if aid in self._spawn_times]
        avg_lifetime = sum(lifetimes) / len(lifetimes) if lifetimes else 0.0

        type_counts: dict[str, int] = defaultdict(int)
        for agent in self._active.values():
            spec_name = getattr(getattr(agent, "spec", None), "name", "unknown")
            type_counts[spec_name] += 1

        return {
            "active_count": len(self._active),
            "max_concurrent": MAX_CONCURRENT_EPHEMERAL,
            "avg_lifetime_s": round(avg_lifetime, 1),
            "by_type": dict(type_counts),
            "pool": self._pool.stats(),
        }

    def heat_map(self) -> dict[str, int]:
        """Usage frequency by agent type (spec name) — all-time spawn count."""
        return dict(self._heat)

    # ── Legacy compatibility ───────────────────────────────────────────────

    def list_active(self) -> list[str]:
        """Return IDs of all currently active ephemeral agents."""
        return list(self._active)

    def get(self, agent_id: str) -> EphemeralAgent:
        try:
            return self._active[agent_id]
        except KeyError:
            raise KeyError(f"Ephemeral agent '{agent_id}' is not active.")
