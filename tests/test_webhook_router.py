from __future__ import annotations

import asyncio
import pathlib

from sovereign.infra.webhooks import WebhookEvent, WebhookRouter


def _router(tmp_path: pathlib.Path) -> WebhookRouter:
    return WebhookRouter(data_path=tmp_path / "webhooks.jsonl")


def test_receive_creates_event(tmp_path: pathlib.Path):
    router = _router(tmp_path)
    event = asyncio.run(router.receive("github", "push", {"ref": "main"}))
    assert isinstance(event, WebhookEvent)
    assert event.source == "github"
    assert event.event_type == "push"


def test_register_and_dispatch(tmp_path: pathlib.Path):
    router = _router(tmp_path)
    calls = []
    router.register("github", "push", lambda e: calls.append(e) or True)
    asyncio.run(router.receive("github", "push", {"ref": "main"}))
    assert len(calls) == 1
    assert calls[0].source == "github"


def test_unregister(tmp_path: pathlib.Path):
    router = _router(tmp_path)
    calls = []
    handler_id = router.register("github", "push", lambda e: calls.append(e) or True)
    router.unregister(handler_id)
    asyncio.run(router.receive("github", "push", {"ref": "main"}))
    assert calls == []


def test_stats_increment(tmp_path: pathlib.Path):
    router = _router(tmp_path)
    asyncio.run(router.receive("github", "push", {"ref": "main"}))
    asyncio.run(router.receive("github", "push", {"ref": "dev"}))
    assert router.stats()["total"] == 2


def test_wildcard_handler(tmp_path: pathlib.Path):
    router = _router(tmp_path)
    calls = []
    router.register("*", "*", lambda e: calls.append(e) or True)
    asyncio.run(router.receive("stripe", "payment", {"amount": 100}))
    asyncio.run(router.receive("github", "push", {"ref": "main"}))
    assert len(calls) == 2
