"""Tests for ConversationStore — sovereign.memory.conversation_store."""
from __future__ import annotations

import pathlib


from sovereign.memory.conversation_store import ConversationStore, get_conversation_store


def _make_store(tmp_path: pathlib.Path) -> ConversationStore:
    return ConversationStore(data_dir=tmp_path / "conversations")


def test_append_and_recent(tmp_path: pathlib.Path):
    store = _make_store(tmp_path)
    store.append("conv1", "user", "Hello")
    store.append("conv1", "assistant", "Hi there")
    store.append("conv1", "user", "How are you?")

    turns = store.recent("conv1", n=10)
    assert len(turns) == 3
    assert turns[0].role == "user"
    assert turns[0].content == "Hello"
    assert turns[1].role == "assistant"
    assert turns[1].content == "Hi there"
    assert turns[2].role == "user"
    assert turns[2].content == "How are you?"


def test_ring_buffer(tmp_path: pathlib.Path):
    store = ConversationStore(data_dir=tmp_path / "conversations", max_turns=20)
    for i in range(25):
        role = "user" if i % 2 == 0 else "assistant"
        store.append("conv_ring", role, f"message {i}")

    turns = store.recent("conv_ring", n=20)
    assert len(turns) == 20
    assert turns[-1].content == "message 24"
    assert turns[0].content == "message 5"


def test_to_messages_format(tmp_path: pathlib.Path):
    store = _make_store(tmp_path)
    store.append("conv2", "user", "Question")
    store.append("conv2", "assistant", "Answer")

    messages = store.to_messages("conv2", n=10)
    assert isinstance(messages, list)
    assert len(messages) == 2
    for msg in messages:
        assert "role" in msg
        assert "content" in msg
        assert isinstance(msg["role"], str)
        assert isinstance(msg["content"], str)
    assert messages[0] == {"role": "user", "content": "Question"}
    assert messages[1] == {"role": "assistant", "content": "Answer"}


def test_to_context_string(tmp_path: pathlib.Path):
    store = _make_store(tmp_path)
    store.append("conv3", "user", "Tell me something")
    store.append("conv3", "assistant", "Here is something interesting")

    result = store.to_context_string("conv3")
    assert isinstance(result, str)
    assert len(result) > 0


def test_clear(tmp_path: pathlib.Path):
    store = _make_store(tmp_path)
    store.append("conv4", "user", "One")
    store.append("conv4", "assistant", "Two")

    store.clear("conv4")
    turns = store.recent("conv4", n=10)
    assert turns == []


def test_list_conversations(tmp_path: pathlib.Path):
    store = _make_store(tmp_path)
    store.append("alice", "user", "Hello")
    store.append("bob", "user", "Hi")
    store.append("charlie", "assistant", "Hey")

    conversations = store.list_conversations()
    assert set(conversations) >= {"alice", "bob", "charlie"}


def test_singleton(tmp_path: pathlib.Path):
    import sovereign.memory.conversation_store as cs_mod

    original = cs_mod._store
    cs_mod._store = None
    try:
        store_a = get_conversation_store()
        store_b = get_conversation_store()
        assert store_a is store_b
    finally:
        cs_mod._store = original
