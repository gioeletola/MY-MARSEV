from __future__ import annotations

import asyncio

from sovereign.infra.watchdog import ProcessWatchdog


def _run_for(coro, timeout: float = 0.5):
    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


def test_register_shows_in_status():
    wd = ProcessWatchdog()
    wd.register("worker", lambda: asyncio.sleep(0))
    status = wd.get_status()
    assert "worker" in status


def test_health_summary_empty():
    wd = ProcessWatchdog()
    summary = wd.health_summary()
    assert summary["names"] == []
    assert summary["total_restarts"] == 0


def test_health_summary_after_register():
    wd = ProcessWatchdog()
    wd.register("svc", lambda: asyncio.sleep(0))
    summary = wd.health_summary()
    assert len(summary["names"]) == 1
    assert "svc" in summary["names"]


def test_supervise_restarts_on_failure():
    call_count = {"n": 0}

    async def flaky():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ValueError("boom")
        await asyncio.sleep(10)

    wd = ProcessWatchdog()
    wd.register("flaky", flaky, alert_threshold=1)

    async def _run():
        stop = asyncio.Event()
        task = asyncio.create_task(wd.start_all(stop))
        await asyncio.sleep(0.3)
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()

    _run_for(_run(), timeout=2.0)
    assert wd.get_status()["flaky"]["restart_count"] >= 1


def test_alert_callback_fires():
    alerts = []

    async def always_fails():
        raise RuntimeError("always fails")

    wd = ProcessWatchdog(alert_callback=lambda name, exc: alerts.append((name, exc)))
    wd.register("bad", always_fails, alert_threshold=1)

    async def _run():
        stop = asyncio.Event()
        task = asyncio.create_task(wd.start_all(stop))
        await asyncio.sleep(0.2)
        stop.set()
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()

    _run_for(_run(), timeout=2.0)
    assert len(alerts) >= 1
    assert alerts[0][0] == "bad"
    assert isinstance(alerts[0][1], RuntimeError)
