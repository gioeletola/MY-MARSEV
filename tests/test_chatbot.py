"""Tests for sovereign/chatbot/ — ConversationEngine, SessionStore, types."""
from __future__ import annotations

import pytest

from sovereign.chatbot import ChatSession, ChatResponse, ConversationEngine, MessageRole, SessionStatus
from sovereign.chatbot.session_store import SessionStore


class TestChatSession:
    def test_add_message(self):
        s = ChatSession()
        msg = s.add_message(MessageRole.USER, "hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "hello"
        assert len(s.messages) == 1

    def test_to_api_messages_excludes_system(self):
        s = ChatSession()
        s.add_message(MessageRole.SYSTEM, "sys")
        s.add_message(MessageRole.USER, "hi")
        api = s.to_api_messages()
        assert len(api) == 1
        assert api[0]["role"] == "user"

    def test_last_n(self):
        s = ChatSession()
        for i in range(10):
            s.add_message(MessageRole.USER, str(i))
        assert len(s.last_n(3)) == 3
        assert s.last_n(3)[-1].content == "9"

    def test_clear(self):
        s = ChatSession()
        s.add_message(MessageRole.USER, "hi")
        s.clear()
        assert s.messages == []
        assert s.token_count == 0


class TestSessionStore:
    def test_create_and_get(self):
        store = SessionStore()
        sess = store.create(title="Test")
        assert store.get(sess.session_id) is sess

    def test_delete(self):
        store = SessionStore()
        sess = store.create()
        assert store.delete(sess.session_id)
        assert store.get(sess.session_id) is None

    def test_list_sessions(self):
        store = SessionStore()
        store.create(title="A")
        store.create(title="B")
        assert len(store.list_sessions()) >= 2

    def test_end_session(self):
        store = SessionStore()
        sess = store.create()
        store.end_session(sess.session_id)
        assert store.get(sess.session_id).status == SessionStatus.ENDED

    def test_persist_and_reload(self, tmp_path):
        path = tmp_path / "sessions.json"
        store = SessionStore(persist_path=path)
        sess = store.create(title="Persist Test")
        sess.add_message(MessageRole.USER, "hello world")
        store.save()
        store2 = SessionStore(persist_path=path)
        loaded = store2.get(sess.session_id)
        assert loaded is not None
        assert loaded.title == "Persist Test"
        assert loaded.messages[0].content == "hello world"


class TestConversationEngine:
    @pytest.mark.asyncio
    async def test_chat_stub_mode(self):
        engine = ConversationEngine()
        session = ChatSession()
        resp = await engine.chat(session, "hello")
        assert isinstance(resp, ChatResponse)
        assert resp.success

    @pytest.mark.asyncio
    async def test_chat_adds_messages(self):
        engine = ConversationEngine()
        session = ChatSession()
        await engine.chat(session, "test message")
        assert len(session.messages) == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_stream_stub_mode(self):
        engine = ConversationEngine()
        session = ChatSession()
        chunks = []
        async for chunk in engine.stream_chat(session, "stream test"):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert len(session.messages) == 2
