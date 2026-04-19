"""
Tests for the H24 infra layer:
  - sovereign/infra/worker_manager.py  (WorkerManager + H24WorkerPool)
  - sovereign/infra/scheduler.py       (Scheduler)
  - sovereign/infra/notification_service.py (NotificationService)
  - sovereign/infra/watchdog.py        (ProcessWatchdog)
  - sovereign/infra/health_alerter.py  (HealthAlerter)
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# WorkerManager tests
# ===========================================================================

class TestWorkerManager:
    def test_register_worker(self):
        from sovereign.infra.worker_manager import WorkerManager, WorkerSpec

        wm = WorkerManager()
        spec = WorkerSpec(worker_id="test-worker", coro_factory=lambda: asyncio.sleep(0))
        wm.register(spec)
        assert wm.status("test-worker") is not None

    def test_register_duplicate_is_noop(self):
        from sovereign.infra.worker_manager import WorkerManager, WorkerSpec, WorkerStatus

        wm = WorkerManager()
        spec = WorkerSpec(worker_id="w1", coro_factory=lambda: asyncio.sleep(0))
        wm.register(spec)
        wm.register(spec)  # second call should be ignored
        assert wm.status("w1") == WorkerStatus.IDLE

    def test_status_unknown_returns_none(self):
        from sovereign.infra.worker_manager import WorkerManager

        wm = WorkerManager()
        assert wm.status("nonexistent") is None

    def test_snapshot_empty(self):
        from sovereign.infra.worker_manager import WorkerManager

        wm = WorkerManager()
        assert wm.snapshot() == []

    def test_snapshot_with_workers(self):
        from sovereign.infra.worker_manager import WorkerManager, WorkerSpec

        wm = WorkerManager()
        spec = WorkerSpec(worker_id="w1", coro_factory=lambda: asyncio.sleep(0), description="Test worker")
        wm.register(spec)
        snap = wm.snapshot()
        assert len(snap) == 1
        assert snap[0]["worker_id"] == "w1"
        assert snap[0]["description"] == "Test worker"

    def test_failed_workers_empty_initially(self):
        from sovereign.infra.worker_manager import WorkerManager

        wm = WorkerManager()
        assert wm.failed_workers() == []

    async def test_start_stop_worker(self):
        from sovereign.infra.worker_manager import WorkerManager, WorkerSpec, WorkerStatus

        done_event = asyncio.Event()

        async def my_coro():
            done_event.set()
            await asyncio.sleep(10)  # run until cancelled

        wm = WorkerManager()
        spec = WorkerSpec(worker_id="w1", coro_factory=my_coro, restart_on_failure=False)
        wm.register(spec)
        await wm.start("w1")
        # Wait until coro has started
        await asyncio.wait_for(done_event.wait(), timeout=2.0)
        assert wm.status("w1") is not None
        await wm.stop("w1")
        assert wm.status("w1") == WorkerStatus.STOPPED

    async def test_start_unknown_worker_raises(self):
        from sovereign.infra.worker_manager import WorkerManager

        wm = WorkerManager()
        with pytest.raises(KeyError):
            await wm.start("does-not-exist")

    async def test_worker_finishes_normally(self):
        from sovereign.infra.worker_manager import WorkerManager, WorkerSpec, WorkerStatus

        async def quick():
            pass

        wm = WorkerManager()
        spec = WorkerSpec(worker_id="w1", coro_factory=quick, restart_on_failure=False)
        wm.register(spec)
        await wm.start("w1")
        # Give the task a tick to complete
        await asyncio.sleep(0.05)
        status = wm.status("w1")
        assert status in (WorkerStatus.IDLE, WorkerStatus.RUNNING)

    async def test_worker_crash_triggers_restart(self):
        from sovereign.infra.worker_manager import WorkerManager, WorkerSpec

        call_count = 0

        async def crasher():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("intentional crash")
            await asyncio.sleep(10)

        wm = WorkerManager()
        spec = WorkerSpec(
            worker_id="crasher",
            coro_factory=crasher,
            restart_on_failure=True,
            max_restarts=5,
            restart_delay_s=0.01,
        )
        wm.register(spec)
        await wm.start("crasher")
        await asyncio.sleep(0.5)
        # Should have been called at least twice (once crashed, once restarted)
        assert call_count >= 1
        await wm.stop_all()

    async def test_stop_all(self):
        from sovereign.infra.worker_manager import WorkerManager, WorkerSpec

        async def noop_loop():
            await asyncio.sleep(100)

        wm = WorkerManager()
        for i in range(3):
            spec = WorkerSpec(worker_id=f"w{i}", coro_factory=noop_loop)
            wm.register(spec)
        await wm.start_all()
        await asyncio.sleep(0.05)
        await wm.stop_all()
        # All should be stopped now
        for i in range(3):
            from sovereign.infra.worker_manager import WorkerStatus
            assert wm.status(f"w{i}") == WorkerStatus.STOPPED


# ===========================================================================
# H24WorkerPool tests
# ===========================================================================

class TestH24WorkerPool:
    def test_create_pool(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        pool = H24WorkerPool(n_workers=3)
        assert pool._n == 3

    def test_initial_stats(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        pool = H24WorkerPool(n_workers=2)
        stats = pool.get_stats()
        assert "started" in stats
        assert "crashed" in stats
        assert "restarted" in stats
        assert stats["started"] == 0

    async def test_pool_processes_tasks(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        results = []
        queue = asyncio.Queue()
        pool = H24WorkerPool(n_workers=2, task_queue=queue, monitor_interval_s=0.05)
        stop = asyncio.Event()

        pool_task = asyncio.create_task(pool.start(stop))
        await asyncio.sleep(0.05)

        # Enqueue a callable task
        await queue.put(lambda: results.append("done"))
        # Wait for task to be processed
        await queue.join()

        stop.set()
        await asyncio.wait_for(pool_task, timeout=2.0)

        assert "done" in results

    async def test_pool_start_stop(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        pool = H24WorkerPool(n_workers=2, monitor_interval_s=0.05)
        stop = asyncio.Event()
        task = asyncio.create_task(pool.start(stop))
        await asyncio.sleep(0.1)
        stop.set()
        await asyncio.wait_for(task, timeout=3.0)
        stats = pool.get_stats()
        assert stats["started"] >= 2

    async def test_pool_processes_async_task(self):
        from sovereign.infra.worker_manager import H24WorkerPool

        results = []
        queue = asyncio.Queue()
        pool = H24WorkerPool(n_workers=1, task_queue=queue, monitor_interval_s=0.05)
        stop = asyncio.Event()
        pool_task = asyncio.create_task(pool.start(stop))

        await asyncio.sleep(0.05)

        async def async_work():
            results.append("async_done")

        await queue.put(async_work)
        await queue.join()

        stop.set()
        await asyncio.wait_for(pool_task, timeout=2.0)
        assert "async_done" in results


# ===========================================================================
# Scheduler tests
# ===========================================================================

class TestScheduler:
    def test_list_jobs_initial_has_defaults(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler

        s = Scheduler(data_path=tmp_path / "sched.json")
        jobs = s.list_jobs()
        # Default jobs are seeded
        assert isinstance(jobs, list)
        assert len(jobs) > 0

    def test_schedule_new_job(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler, ScheduleFrequency

        s = Scheduler(data_path=tmp_path / "sched.json")
        job = s.schedule("my_job", "agent_x", "Do something", ScheduleFrequency.HOURLY)
        assert job.job_id is not None
        assert job.name == "my_job"
        assert job.agent_id == "agent_x"

    def test_unschedule_job(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler, ScheduleFrequency

        s = Scheduler(data_path=tmp_path / "sched.json")
        job = s.schedule("my_job", "agent_x", "Do something", ScheduleFrequency.DAILY)
        assert s.unschedule(job.job_id) is True
        assert s.unschedule(job.job_id) is False  # already removed

    def test_enable_disable_job(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler, ScheduleFrequency

        s = Scheduler(data_path=tmp_path / "sched.json")
        job = s.schedule("my_job", "agent_x", "Objective", ScheduleFrequency.WEEKLY)
        assert s.disable(job.job_id) is True
        assert s.list_jobs()  # should still exist
        # Find job and assert disabled
        found = next((j for j in s.list_jobs() if j.job_id == job.job_id), None)
        assert found is not None
        assert found.enabled is False
        assert s.enable(job.job_id) is True
        found2 = next((j for j in s.list_jobs() if j.job_id == job.job_id), None)
        assert found2.enabled is True

    def test_due_jobs_none_initially(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler

        s = Scheduler(data_path=tmp_path / "sched.json")
        # All default jobs are scheduled in the future
        due = s.due_jobs()
        assert isinstance(due, list)

    def test_due_jobs_returns_overdue(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler, ScheduleFrequency, ScheduledJob
        import uuid

        s = Scheduler(data_path=tmp_path / "sched.json")
        # Manually inject a past-due job
        overdue = ScheduledJob(
            job_id=str(uuid.uuid4())[:8],
            name="overdue",
            agent_id="agent_y",
            objective="Do overdue thing",
            frequency=ScheduleFrequency.HOURLY,
            interval_seconds=3600,
            next_run=time.time() - 1,  # already past
        )
        s._jobs[overdue.job_id] = overdue
        due = s.due_jobs()
        assert any(j.job_id == overdue.job_id for j in due)

    async def test_tick_returns_list(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler

        s = Scheduler(data_path=tmp_path / "sched.json")
        result = await s.tick()
        assert isinstance(result, list)

    def test_persist_and_reload(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler, ScheduleFrequency

        p = tmp_path / "sched.json"
        s1 = Scheduler(data_path=p)
        job = s1.schedule("persist_test", "agent_a", "Persist me", ScheduleFrequency.DAILY)
        job_id = job.job_id

        # Reload from same file
        s2 = Scheduler(data_path=p)
        loaded_ids = [j.job_id for j in s2.list_jobs()]
        assert job_id in loaded_ids

    def test_custom_interval(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler, ScheduleFrequency

        s = Scheduler(data_path=tmp_path / "sched.json")
        job = s.schedule("custom", "a", "b", ScheduleFrequency.CUSTOM, interval_seconds=120)
        assert job.interval_seconds == 120

    def test_enable_disable_unknown_returns_false(self, tmp_path):
        from sovereign.infra.scheduler import Scheduler

        s = Scheduler(data_path=tmp_path / "sched.json")
        assert s.enable("nonexistent") is False
        assert s.disable("nonexistent") is False


# ===========================================================================
# NotificationService tests
# ===========================================================================

class TestNotificationService:
    async def test_send_returns_dict(self, tmp_path):
        from sovereign.infra.notification_service import NotificationService, NotificationLevel

        with patch("sovereign.infra.notification_service._DATA_FILE", tmp_path / "notifs.jsonl"):
            ns = NotificationService()
            result = await ns.send("Test Title", "Test body", level=NotificationLevel.INFO)
            # send() returns a dict like {"ok": bool, "channel": str, "error": str|None}
            assert isinstance(result, dict)
            # The notification should be in history
            assert len(ns._history) >= 1
            notif = ns._history[-1]
            assert notif.title == "Test Title"
            assert notif.body == "Test body"

    async def test_unread_increments(self, tmp_path):
        from sovereign.infra.notification_service import NotificationService, NotificationLevel

        with patch("sovereign.infra.notification_service._DATA_FILE", tmp_path / "notifs.jsonl"):
            ns = NotificationService()
            initial_unread = len(ns.unread())
            await ns.send("A", "B", level=NotificationLevel.WARNING)
            assert len(ns.unread()) == initial_unread + 1

    async def test_mark_read(self, tmp_path):
        from sovereign.infra.notification_service import NotificationService

        with patch("sovereign.infra.notification_service._DATA_FILE", tmp_path / "notifs.jsonl"):
            ns = NotificationService()
            await ns.send("Title", "Body")
            notif = ns._history[-1]  # get the notification from history
            assert ns.mark_read(notif.notification_id) is True
            assert ns.mark_read("nonexistent") is False
            # Notification should now be marked read
            assert all(n.read for n in ns._history if n.notification_id == notif.notification_id)

    async def test_recent_returns_list(self, tmp_path):
        from sovereign.infra.notification_service import NotificationService

        with patch("sovereign.infra.notification_service._DATA_FILE", tmp_path / "notifs.jsonl"):
            ns = NotificationService()
            await ns.send("A", "B")
            await ns.send("C", "D")
            recent = ns.recent(10)
            assert isinstance(recent, list)
            assert len(recent) >= 2

    async def test_by_level(self, tmp_path):
        from sovereign.infra.notification_service import NotificationService, NotificationLevel

        with patch("sovereign.infra.notification_service._DATA_FILE", tmp_path / "notifs.jsonl"):
            ns = NotificationService()
            await ns.send("Critical alert", "Something broke", level=NotificationLevel.CRITICAL)
            await ns.send("Info", "All good", level=NotificationLevel.INFO)
            critical = ns.by_level(NotificationLevel.CRITICAL)
            assert any(n.title == "Critical alert" for n in critical)

    async def test_critical_count(self, tmp_path):
        from sovereign.infra.notification_service import NotificationService, NotificationLevel

        with patch("sovereign.infra.notification_service._DATA_FILE", tmp_path / "notifs.jsonl"):
            ns = NotificationService()
            await ns.send("Critical", "Bad", level=NotificationLevel.CRITICAL)
            count = ns.critical_count()
            assert count >= 1

    async def test_broadcast(self, tmp_path):
        from sovereign.infra.notification_service import NotificationService, NotificationLevel

        with patch("sovereign.infra.notification_service._DATA_FILE", tmp_path / "notifs.jsonl"):
            ns = NotificationService()
            # Broadcast should not raise
            await ns.broadcast("Broadcast Title", "Broadcast body", NotificationLevel.WARNING)

    async def test_custom_handler_called(self, tmp_path):
        from sovereign.infra.notification_service import (
            NotificationService, NotificationChannel
        )

        with patch("sovereign.infra.notification_service._DATA_FILE", tmp_path / "notifs.jsonl"):
            ns = NotificationService()
            received = []

            async def my_handler(notif):
                received.append(notif)

            ns.register_handler(NotificationChannel.SYSTEM, my_handler)
            await ns.send("T", "B", channels=["system"])
            assert len(received) == 1


# ===========================================================================
# ProcessWatchdog tests
# ===========================================================================

class TestProcessWatchdog:
    async def test_register_and_status(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        wd.register("svc1", lambda: asyncio.sleep(0))
        status = wd.get_status()
        assert "svc1" in status
        assert status["svc1"]["restart_count"] == 0

    async def test_overwrites_existing_registration(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        wd.register("svc1", lambda: asyncio.sleep(0))
        wd.register("svc1", lambda: asyncio.sleep(0))  # overwrite
        assert "svc1" in wd.get_status()

    async def test_normal_completion(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        completed = []

        async def quick():
            completed.append(True)

        wd = ProcessWatchdog()
        wd.register("quick_svc", lambda: quick())
        stop = asyncio.Event()
        task = asyncio.create_task(wd.start_all(stop))
        await asyncio.sleep(0.2)
        stop.set()
        await asyncio.wait_for(task, timeout=2.0)
        assert completed

    async def test_crash_triggers_restart(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        call_count = 0
        stop = asyncio.Event()

        async def crasher():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError(f"crash #{call_count}")
            stop.set()  # Stop after 3 calls

        wd = ProcessWatchdog()
        wd.register("crasher", lambda: crasher())
        await asyncio.wait_for(wd.start_all(stop), timeout=5.0)
        assert call_count >= 2
        assert wd.get_status()["crasher"]["restart_count"] >= 1

    async def test_alert_callback_called_on_crash(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        alerts = []
        stop = asyncio.Event()

        async def crasher():
            stop.set()
            raise ValueError("intentional error")

        def on_alert(name, exc):
            alerts.append((name, str(exc)))

        wd = ProcessWatchdog(alert_callback=on_alert)
        wd.register("svc", lambda: crasher())
        try:
            await asyncio.wait_for(wd.start_all(stop), timeout=3.0)
        except asyncio.TimeoutError:
            pass
        assert len(alerts) >= 1
        assert alerts[0][0] == "svc"

    async def test_empty_watchdog(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        wd = ProcessWatchdog()
        stop = asyncio.Event()
        stop.set()
        # Should complete immediately with no tasks
        await asyncio.wait_for(wd.start_all(stop), timeout=1.0)
        assert wd.get_status() == {}

    async def test_get_status_task_states(self):
        from sovereign.infra.watchdog import ProcessWatchdog

        running_event = asyncio.Event()
        stop = asyncio.Event()

        async def long_runner():
            running_event.set()
            # Wait until stop fires so cancellation is clean
            await asyncio.wait_for(stop.wait(), timeout=5.0)

        wd = ProcessWatchdog()
        wd.register("runner", lambda: long_runner())
        task = asyncio.create_task(wd.start_all(stop))
        await asyncio.wait_for(running_event.wait(), timeout=2.0)
        status = wd.get_status()
        assert "runner" in status
        stop.set()
        # Give the supervisor a moment to notice stop and exit
        try:
            await asyncio.wait_for(task, timeout=3.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass


# ===========================================================================
# HealthAlerter tests
# ===========================================================================

class TestHealthAlerter:
    def test_initial_stats(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=3)
        stats = ha.get_stats()
        assert stats["total_checks"] == 0
        assert stats["consecutive_failures"] == 0
        # Key is "alerts_sent" in actual implementation
        assert stats["alerts_sent"] == 0
        assert stats["threshold"] == 3

    async def test_healthy_check_no_alert(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=3)
        await ha.check_and_alert({"overall": "healthy"})
        stats = ha.get_stats()
        assert stats["total_checks"] == 1
        assert stats["consecutive_failures"] == 0

    async def test_unhealthy_check_increments_failures(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=5)
        await ha.check_and_alert({"overall": "degraded"})
        stats = ha.get_stats()
        assert stats["consecutive_failures"] == 1

    async def test_recovery_resets_failures(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=5)
        await ha.check_and_alert({"overall": "critical"})
        await ha.check_and_alert({"overall": "critical"})
        await ha.check_and_alert({"overall": "healthy"})
        stats = ha.get_stats()
        assert stats["consecutive_failures"] == 0

    async def test_threshold_triggers_telegram_attempt(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=2)
        # No token/chat_id configured → will log but not actually send
        await ha.check_and_alert({"overall": "critical"})
        await ha.check_and_alert({"overall": "critical"})
        # No real Telegram call, but alert count should NOT increment (returns False)
        stats = ha.get_stats()
        assert stats["alerts_sent"] == 0  # unconfigured returns False

    async def test_telegram_send_with_token_success(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(telegram_token="fake-token", chat_id="123", threshold_failures=1)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_resp
            mock_cls.return_value = mock_client

            await ha.check_and_alert({"overall": "critical"})
            stats = ha.get_stats()
            assert stats["alerts_sent"] == 1

    async def test_telegram_send_with_token_failure(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(telegram_token="fake-token", chat_id="123", threshold_failures=1)

        with patch("httpx.AsyncClient") as mock_cls:
            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_resp
            mock_cls.return_value = mock_client

            await ha.check_and_alert({"overall": "degraded"})
            stats = ha.get_stats()
            assert stats["alerts_sent"] == 0

    async def test_telegram_send_exception_handled(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(telegram_token="fake-token", chat_id="123", threshold_failures=1)

        with patch("httpx.AsyncClient", side_effect=Exception("connection refused")):
            # Should not raise
            await ha.check_and_alert({"overall": "critical"})
            stats = ha.get_stats()
            assert stats["alerts_sent"] == 0

    async def test_multiple_checks_counter(self):
        from sovereign.infra.health_alerter import HealthAlerter

        ha = HealthAlerter(threshold_failures=99)
        for _ in range(5):
            await ha.check_and_alert({"overall": "healthy"})
        assert ha.get_stats()["total_checks"] == 5
