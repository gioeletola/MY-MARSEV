"""Memory compaction — merges old duplicate keys and trims stale entries."""
from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sovereign.memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

_STALE_DAYS = 180
_MAX_KEYS_PER_DOMAIN = 500


class MemoryCompaction:
    """Nightly compaction job.

    For every memory domain:
    1. Removes transient entries (key starts with _tmp_, scratch_, _transient_)
       older than _STALE_DAYS.
    2. Caps domains at _MAX_KEYS_PER_DOMAIN, trimming the oldest entries first.
    3. Writes a compaction report to the operational domain.
    """

    def __init__(self, memory: "MemoryManager") -> None:
        self._memory = memory

    async def run(self) -> dict[str, Any]:
        from sovereign.memory.memory_manager import MEMORY_DOMAINS

        report: dict[str, Any] = {
            "started_at": datetime.datetime.utcnow().isoformat() + "Z",
            "domains": {},
            "total_removed": 0,
        }
        cutoff = (
            datetime.datetime.utcnow() - datetime.timedelta(days=_STALE_DAYS)
        ).isoformat() + "Z"

        for domain in MEMORY_DOMAINS:
            removed = await self._compact_domain(domain, cutoff)
            if removed:
                report["domains"][domain] = removed
                report["total_removed"] += removed

        report["finished_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        logger.info(
            "MemoryCompaction: removed %d stale entries across %d domains",
            report["total_removed"],
            len(report["domains"]),
        )
        await self._save_report(report)
        return report

    async def _compact_domain(self, domain: str, cutoff: str) -> int:
        try:
            keys = await self._memory.list_keys(domain)
        except Exception:
            return 0

        removed = 0
        _TRANSIENT = ("_tmp_", "scratch_", "_transient_")

        for key in list(keys):
            if not any(key.startswith(p) for p in _TRANSIENT):
                continue
            record = await self._memory.read(domain, key)
            if not isinstance(record, dict):
                continue
            ts = record.get("updated_at") or record.get("created_at") or ""
            if ts and ts < cutoff:
                await self._memory.delete(domain, key)
                removed += 1

        keys_after = await self._memory.list_keys(domain)
        if len(keys_after) <= _MAX_KEYS_PER_DOMAIN:
            return removed

        dated: list[tuple[str, str]] = []
        for key in keys_after:
            if key.startswith("_"):
                continue
            record = await self._memory.read(domain, key)
            ts = ""
            if isinstance(record, dict):
                ts = record.get("updated_at") or record.get("created_at") or ""
            dated.append((key, ts))

        dated.sort(key=lambda x: x[1])
        excess = len(keys_after) - _MAX_KEYS_PER_DOMAIN
        for key, _ in dated[:excess]:
            await self._memory.delete(domain, key)
            removed += 1

        return removed

    async def _save_report(self, report: dict[str, Any]) -> None:
        try:
            key = "compaction_" + report["started_at"][:10]
            await self._memory.write("operational", key, report)
        except Exception as exc:
            logger.debug("MemoryCompaction: report save failed: %s", exc)
