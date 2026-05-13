"""Tests for the typed EventBus."""
import pytest
from sovereign.events.event_types import EventType, SovereignEvent
from sovereign.events.event_bus import EventBus


def test_subscribe_and_emit_sync():
    bus = EventBus()
    received = []
    bus.subscribe(EventType.TASK_START, lambda e: received.append(e))
    bus.emit(SovereignEvent(type=EventType.TASK_START, data={"agent": "x"}))
    assert len(received) == 1
    assert received[0].data["agent"] == "x"


def test_wildcard_receives_all():
    bus = EventBus()
    received = []
    bus.subscribe_all(lambda e: received.append(e.type))
    bus.emit(SovereignEvent(type=EventType.TASK_START))
    bus.emit(SovereignEvent(type=EventType.MODE_CHANGE))
    assert EventType.TASK_START in received
    assert EventType.MODE_CHANGE in received


def test_unsubscribe():
    bus = EventBus()
    received = []
    def cb(e):
        received.append(1)
    bus.subscribe(EventType.TOOL_CALL, cb)
    bus.unsubscribe(EventType.TOOL_CALL, cb)
    bus.emit(SovereignEvent(type=EventType.TOOL_CALL))
    assert received == []


def test_specific_type_does_not_fire_on_other():
    bus = EventBus()
    received = []
    bus.subscribe(EventType.TASK_START, lambda e: received.append(1))
    bus.emit(SovereignEvent(type=EventType.TASK_DONE))
    assert received == []


@pytest.mark.asyncio
async def test_async_subscriber():
    bus = EventBus()
    received = []
    async def async_cb(event):
        received.append(event.type)
    bus.subscribe(EventType.STREAM_DONE, async_cb)
    await bus.emit_async(SovereignEvent(type=EventType.STREAM_DONE))
    assert EventType.STREAM_DONE in received


def test_legacy_callback_bridge():
    bus = EventBus()
    received = []
    def legacy_cb(d: dict):
        received.append(d.get("type"))
    bus.add_legacy_callback(legacy_cb)
    bus.emit(SovereignEvent(type=EventType.HEALTH_UPDATE))
    assert "health_update" in received


def test_remove_legacy_callback():
    bus = EventBus()
    received = []
    def legacy_cb(d: dict):
        received.append(1)
    bus.add_legacy_callback(legacy_cb)
    bus.remove_legacy_callback(legacy_cb)
    bus.emit(SovereignEvent(type=EventType.HEALTH_UPDATE))
    assert received == []


def test_event_to_dict():
    e = SovereignEvent(type=EventType.TASK_START, session_id="s1", data={"agent": "ceo"})
    d = e.to_dict()
    assert d["type"] == "task_start"
    assert d["session_id"] == "s1"
    assert d["agent"] == "ceo"


def test_event_from_dict():
    d = {"type": "mode_change", "session_id": "s2", "mode": "finance", "ts": 1234567890.0}
    e = SovereignEvent.from_dict(d)
    assert e.type == EventType.MODE_CHANGE
    assert e.data["mode"] == "finance"


def test_subscriber_count():
    bus = EventBus()
    bus.subscribe(EventType.TASK_START, lambda e: None)
    bus.subscribe(EventType.TASK_START, lambda e: None)
    bus.subscribe_all(lambda e: None)
    assert bus.subscriber_count(EventType.TASK_START) == 2
    assert bus.subscriber_count() >= 3


def test_unknown_event_type_becomes_custom():
    e = SovereignEvent.from_dict({"type": "totally_unknown_event_xyz"})
    assert e.type == EventType.CUSTOM


@pytest.mark.asyncio
async def test_emit_async_multiple_subscribers():
    bus = EventBus()
    results = []
    async def cb1(e): results.append("cb1")
    async def cb2(e): results.append("cb2")
    bus.subscribe(EventType.AGENT_STEP, cb1)
    bus.subscribe(EventType.AGENT_STEP, cb2)
    await bus.emit_async(SovereignEvent(type=EventType.AGENT_STEP))
    assert "cb1" in results and "cb2" in results
