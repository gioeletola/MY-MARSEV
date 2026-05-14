"""Async task scheduler — cron-style recurring jobs."""
from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

_DEFAULT_PATH = pathlib.Path("data/memory/scheduler.json")


class ScheduleFrequency(str, Enum):
    MINUTELY = "minutely"
    HOURLY   = "hourly"
    DAILY    = "daily"
    WEEKLY   = "weekly"
    MONTHLY  = "monthly"
    CUSTOM   = "custom"


_FREQ_SECONDS: dict[str, int] = {
    ScheduleFrequency.MINUTELY: 60,
    ScheduleFrequency.HOURLY:   3600,
    ScheduleFrequency.DAILY:    86400,
    ScheduleFrequency.WEEKLY:   604800,
    ScheduleFrequency.MONTHLY:  2592000,
}


@dataclass
class ScheduledJob:
    job_id:           str
    name:             str
    agent_id:         str
    objective:        str
    frequency:        ScheduleFrequency
    interval_seconds: int
    next_run:         float
    last_run:         float = 0.0
    enabled:          bool  = True
    run_count:        int   = 0
    payload:          dict  = field(default_factory=dict)


class Scheduler:
    def __init__(self, data_path: str | pathlib.Path = _DEFAULT_PATH) -> None:
        self._path = pathlib.Path(data_path)
        self._jobs: dict[str, ScheduledJob] = {}
        self._load()
        if not self._jobs:
            self._seed_defaults()

    def schedule(
        self,
        name: str,
        agent_id: str,
        objective: str,
        frequency: ScheduleFrequency = ScheduleFrequency.DAILY,
        interval_seconds: int = 0,
        payload: dict | None = None,
    ) -> ScheduledJob:
        secs = interval_seconds or _FREQ_SECONDS.get(frequency, 3600)
        job = ScheduledJob(
            job_id=str(uuid.uuid4())[:8],
            name=name,
            agent_id=agent_id,
            objective=objective,
            frequency=frequency,
            interval_seconds=secs,
            next_run=time.time() + secs,
            payload=payload or {},
        )
        self._jobs[job.job_id] = job
        self._persist()
        logger.info("Scheduler: added job '%s' (%s)", name, job.job_id)
        return job

    def unschedule(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._persist()
            return True
        return False

    def enable(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._jobs[job_id].enabled = True
            self._persist()
            return True
        return False

    def disable(self, job_id: str) -> bool:
        if job_id in self._jobs:
            self._jobs[job_id].enabled = False
            self._persist()
            return True
        return False

    def due_jobs(self) -> list[ScheduledJob]:
        now = time.time()
        due = [j for j in self._jobs.values() if j.enabled and j.next_run <= now]
        for j in due:
            j.last_run = now
            j.next_run = now + j.interval_seconds
            j.run_count += 1
        if due:
            self._persist()
        return due

    async def tick(self) -> list[ScheduledJob]:
        return self.due_jobs()

    def list_jobs(self) -> list[ScheduledJob]:
        return list(self._jobs.values())

    async def run_loop(self, queue: object, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                due = self.due_jobs()
                for job in due:
                    try:
                        await queue.enqueue(  # type: ignore[attr-defined]
                            agent_id=job.agent_id,
                            objective=job.objective,
                            payload=job.payload,
                        )
                    except Exception as exc:
                        logger.error("Scheduler: enqueue failed for %s: %s", job.job_id, exc)
            except Exception as exc:
                logger.error("Scheduler tick error: %s", exc)
            await asyncio.sleep(30)

    def _seed_defaults(self) -> None:
        """Register default jobs for a fresh install."""
        self.schedule(
            "daily_health_check", "health_monitor",
            "Run system health check",
            ScheduleFrequency.HOURLY,
        )
        self.schedule(
            "daily_memory_flush", "memory_manager",
            "Flush memory caches to disk",
            ScheduleFrequency.DAILY,
        )
        self.schedule(
            "morning_brief", "morning_loop",
            "Prepare and send morning brief with today's calendar events and urgent tasks via Telegram",
            ScheduleFrequency.DAILY,
        )
        self.schedule(
            "memory_compaction", "memory_compaction",
            "Run nightly memory compaction: remove stale transient entries and trim oversized domains",
            ScheduleFrequency.DAILY,
        )
        self.schedule(
            "weekly_eval_report", "eval_agent",
            "Generate weekly quality eval report from agent feedback",
            ScheduleFrequency.WEEKLY,
        )

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {jid: asdict(j) for jid, j in self._jobs.items()}
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("Scheduler persist failed: %s", exc)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for jid, jdata in data.items():
                jdata["frequency"] = ScheduleFrequency(jdata["frequency"])
                self._jobs[jid] = ScheduledJob(**jdata)
            logger.info("Scheduler: loaded %d jobs", len(self._jobs))
        except Exception as exc:
            logger.warning("Scheduler load failed: %s", exc)
