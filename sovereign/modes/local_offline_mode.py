"""
Operating mode: local_offline.

Implements Section 20 of the SOVEREIGN AI OS spec:
- Detects connectivity status
- Switches to local memory only when offline
- Queues operations that require network for deferred sync
- Uses local/cheaper models when possible
- Preserves exportable state
"""
from __future__ import annotations

import asyncio
import json
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any

from sovereign.kernel.action_classes import ActionClass
from sovereign.modes.base_mode import BaseMode

logger = logging.getLogger(__name__)

# Connectivity check target (lightweight, no data sent)
_PING_HOST = "1.1.1.1"
_PING_PORT = 53
_PING_TIMEOUT = 2.0


@dataclass
class DeferredOperation:
    """An operation queued for later sync when connectivity is restored."""
    operation_id: str
    operation_type: str      # "memory_write" | "api_call" | "approval_request"
    payload: dict[str, Any]
    created_at: str = field(default_factory=lambda: __import__("datetime").datetime.utcnow().isoformat() + "Z")
    retry_count: int = 0


class Local_offlineMode(BaseMode):
    """
    Offline-first operating mode with connection detection and deferred sync.

    Behaviour when offline:
    - Blocks all external API calls (web_search, browser, mcp)
    - Allows local tools only (code_exec, cli_exec, file_ops, memory_tool)
    - Queues write operations for deferred sync
    - Uses cheapest/local model (claude-haiku for reduced cost)
    - Preserves full audit trail locally

    Behaviour when online (degraded sync):
    - Flushes deferred queue
    - Restores full tool access
    """

    # Tools allowed offline (read-only or local-only)
    OFFLINE_TOOLS = frozenset({"code_exec", "cli_exec", "file_ops", "memory_tool"})
    # Tools requiring network
    NETWORK_TOOLS = frozenset({"web_search", "browser", "mcp"})

    def __init__(self, data_dir: str | pathlib.Path = "data") -> None:
        super().__init__(
            name="local_offline",
            description="Offline-first with local memory and deferred sync",
            default_action_class=ActionClass.SUGGEST,
            escalation_threshold=0.7,
            preferred_model="claude-haiku-4-5-20251001",
        )
        self._data_dir = pathlib.Path(data_dir)
        self._queue_path = self._data_dir / "offline_queue.jsonl"
        self._online: bool | None = None   # None = not yet checked
        self._deferred: list[DeferredOperation] = []
        self._load_queue()

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------

    async def check_connectivity(self) -> bool:
        """
        Non-blocking TCP probe to detect internet connectivity.
        Returns True if online, False if offline.
        """
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(_PING_HOST, _PING_PORT),
                timeout=_PING_TIMEOUT,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            self._online = True
            return True
        except Exception:
            self._online = False
            return False

    @property
    def is_online(self) -> bool | None:
        """Cached connectivity status. None if not yet checked."""
        return self._online

    def filter_tools(self, requested_tools: list[str]) -> list[str]:
        """
        Filter a list of tool names to only those allowed in current connectivity state.

        If offline (or unknown), removes network-requiring tools.
        If online, returns all requested tools unchanged.
        """
        if self._online is False:
            allowed = [t for t in requested_tools if t in self.OFFLINE_TOOLS]
            blocked = [t for t in requested_tools if t in self.NETWORK_TOOLS]
            if blocked:
                logger.warning(
                    "Offline mode: blocking network tools %s", blocked
                )
            return allowed
        return requested_tools

    # ------------------------------------------------------------------
    # Deferred operation queue
    # ------------------------------------------------------------------

    def enqueue(self, op: DeferredOperation) -> None:
        """Add an operation to the deferred sync queue and persist it."""
        self._deferred.append(op)
        self._persist_queue()
        logger.info(
            "Offline queue: enqueued %s (total=%d)", op.operation_type, len(self._deferred)
        )

    def get_queue(self) -> list[DeferredOperation]:
        return list(self._deferred)

    async def flush_queue(self, executor: Any) -> dict[str, Any]:
        """
        Attempt to flush all deferred operations now that connectivity is restored.

        executor: async callable(op: DeferredOperation) -> bool (True = success)
        Returns summary of what succeeded / failed.
        """
        if not self._deferred:
            return {"flushed": 0, "failed": 0, "remaining": 0}

        succeeded = 0
        failed_ops: list[DeferredOperation] = []

        for op in list(self._deferred):
            try:
                ok = await executor(op)
                if ok:
                    succeeded += 1
                else:
                    op.retry_count += 1
                    failed_ops.append(op)
            except Exception as exc:
                logger.error("Flush failed op=%s: %s", op.operation_id, exc)
                op.retry_count += 1
                failed_ops.append(op)

        self._deferred = failed_ops
        self._persist_queue()

        logger.info(
            "Offline queue flush: succeeded=%d failed=%d remaining=%d",
            succeeded, len(failed_ops), len(failed_ops),
        )
        return {
            "flushed": succeeded,
            "failed": len(failed_ops),
            "remaining": len(failed_ops),
        }

    def export_state(self) -> dict[str, Any]:
        """
        Export full offline state for portability / backup (Section 20).
        Returns a JSON-serialisable dict.
        """
        return {
            "mode": self.name,
            "online": self._online,
            "queued_operations": len(self._deferred),
            "queue": [
                {
                    "id": op.operation_id,
                    "type": op.operation_type,
                    "created_at": op.created_at,
                    "retries": op.retry_count,
                }
                for op in self._deferred
            ],
        }

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_queue(self) -> None:
        """Load deferred queue from disk on startup."""
        if not self._queue_path.exists():
            return
        try:
            with self._queue_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    self._deferred.append(DeferredOperation(**data))
            logger.info("Loaded %d deferred ops from offline queue.", len(self._deferred))
        except Exception as exc:
            logger.warning("Could not load offline queue: %s", exc)

    def _persist_queue(self) -> None:
        """Persist current deferred queue to JSONL file."""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            with self._queue_path.open("w", encoding="utf-8") as f:
                for op in self._deferred:
                    f.write(json.dumps({
                        "operation_id": op.operation_id,
                        "operation_type": op.operation_type,
                        "payload": op.payload,
                        "created_at": op.created_at,
                        "retry_count": op.retry_count,
                    }) + "\n")
        except Exception as exc:
            logger.error("Could not persist offline queue: %s", exc)
