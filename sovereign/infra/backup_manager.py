"""Automated memory backup — archives data/ to data/backups/ on a schedule."""
from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupManager:
    def __init__(self, data_dir: str = "data", max_backups: int = 7) -> None:
        self._data = Path(data_dir)
        self._backup_dir = self._data / "backups"
        self._max = max_backups

    async def run_loop(
        self,
        interval_hours: float = 24,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Run backup every interval_hours. Call once at startup."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                await self._do_backup()
            except Exception as exc:
                logger.error("Backup failed: %s", exc)
            if stop_event is not None:
                try:
                    await asyncio.wait_for(
                        asyncio.shield(stop_event.wait()),
                        timeout=interval_hours * 3600,
                    )
                    break
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(interval_hours * 3600)

    async def _do_backup(self) -> None:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dest = self._backup_dir / f"memory_{ts}"
        src = self._data / "memory"
        if not src.exists():
            logger.debug("Backup skipped — %s does not exist", src)
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, shutil.copytree, str(src), str(dest))
        logger.info("Memory backup created: %s", dest)
        await self._prune()

    async def _prune(self) -> None:
        backups = sorted(self._backup_dir.glob("memory_*"))
        while len(backups) > self._max:
            shutil.rmtree(backups.pop(0), ignore_errors=True)

    def list_backups(self) -> list[str]:
        """Return sorted list of backup directory paths."""
        return sorted(str(p) for p in self._backup_dir.glob("memory_*"))

    def restore(self, backup_name: str) -> None:
        """Restore a named backup over data/memory/."""
        src = self._backup_dir / backup_name
        dest = self._data / "memory"
        if not src.exists():
            raise FileNotFoundError(f"Backup not found: {backup_name}")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(str(src), str(dest))
        logger.info("Memory restored from: %s", backup_name)
