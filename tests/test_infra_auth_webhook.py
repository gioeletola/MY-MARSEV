"""
Tests for sovereign/infra/auth.py and sovereign/infra/webhooks.py.
"""
from __future__ import annotations

import asyncio
import pytest


# ===========================================================================
# AuthManager
# ===========================================================================

class TestAuthManager:
    @pytest.fixture
    def manager(self, tmp_path):
        from sovereign.infra.auth import AuthManager
        return AuthManager(revoke_path=tmp_path / "revoked.json")

    def test_create_token_returns_string(self, manager):
        token = manager.create_token("alice", "admin")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_verify_valid_token(self, manager):
        token = manager.create_token("alice", "admin")
        payload = manager.verify_token(token)
        assert payload is not None
        assert payload.subject == "alice"
        assert payload.role == "admin"

    def test_verify_token_fields(self, manager):
        token = manager.create_token("bob", "user", expires_in_seconds=3600)
        payload = manager.verify_token(token)
        assert payload.session_id is not None
        assert payload.issued_at < payload.expires_at

    def test_verify_expired_token(self, manager):
        token = manager.create_token("alice", "admin", expires_in_seconds=-1)
        payload = manager.verify_token(token)
        assert payload is None

    def test_verify_invalid_signature(self, manager):
        token = manager.create_token("alice", "admin")
        parts = token.split(".")
        tampered = parts[0] + "." + parts[1] + ".invalidsig"
        assert manager.verify_token(tampered) is None

    def test_verify_wrong_format(self, manager):
        assert manager.verify_token("not.a.valid.token.here") is None
        assert manager.verify_token("onlytwoparts.here") is None

    def test_verify_garbage_token(self, manager):
        assert manager.verify_token("garbage") is None

    def test_revoke_token(self, manager):
        token = manager.create_token("alice", "admin")
        assert not manager.is_revoked(token)
        manager.revoke_token(token)
        assert manager.is_revoked(token)

    def test_verify_revoked_token_returns_none(self, manager):
        token = manager.create_token("alice", "admin")
        manager.revoke_token(token)
        assert manager.verify_token(token) is None

    def test_revoke_persists(self, tmp_path):
        from sovereign.infra.auth import AuthManager
        path = tmp_path / "revoked.json"
        m1 = AuthManager(revoke_path=path)
        token = m1.create_token("alice", "admin")
        m1.revoke_token(token)
        m2 = AuthManager(revoke_path=path)
        assert m2.is_revoked(token)

    def test_not_revoked_by_default(self, manager):
        token = manager.create_token("alice", "admin")
        assert not manager.is_revoked(token)

    def test_different_subjects_different_tokens(self, manager):
        t1 = manager.create_token("alice", "admin")
        t2 = manager.create_token("bob", "user")
        assert t1 != t2

    def test_load_missing_revoke_file(self, tmp_path):
        from sovereign.infra.auth import AuthManager
        m = AuthManager(revoke_path=tmp_path / "nonexistent.json")
        assert m.verify_token(m.create_token("x", "y")) is not None

    def test_token_with_custom_expiry(self, manager):
        token = manager.create_token("user", "viewer", expires_in_seconds=7200)
        payload = manager.verify_token(token)
        assert payload is not None
        assert (payload.expires_at - payload.issued_at) > 7000


# ===========================================================================
# WebhookRouter
# ===========================================================================

class TestWebhookRouter:
    @pytest.fixture
    def router(self, tmp_path):
        from sovereign.infra.webhooks import WebhookRouter
        return WebhookRouter(data_path=tmp_path / "hooks.jsonl")

    @pytest.mark.asyncio
    async def test_receive_no_handlers(self, router):
        event = await router.receive("github", "push", {"ref": "main"})
        assert event.source == "github"
        assert event.event_type == "push"
        assert event.event_id is not None

    @pytest.mark.asyncio
    async def test_receive_calls_handler(self, router):
        calls = []

        def handler(evt):
            calls.append(evt.event_id)
            return True

        router.register("github", "push", handler)
        event = await router.receive("github", "push", {})
        assert len(calls) == 1
        assert event.processed is True

    @pytest.mark.asyncio
    async def test_receive_async_handler(self, router):
        calls = []

        async def handler(evt):
            calls.append(evt.event_id)
            return True

        router.register("github", "push", handler)
        await router.receive("github", "push", {})
        assert len(calls) == 1

    def test_register_returns_id(self, router):
        handler_id = router.register("src", "type", lambda e: True)
        assert isinstance(handler_id, str)
        assert len(handler_id) > 0

    def test_unregister_existing(self, router):
        hid = router.register("src", "type", lambda e: True)
        assert router.unregister(hid) is True

    def test_unregister_nonexistent(self, router):
        assert router.unregister("ghost") is False

    @pytest.mark.asyncio
    async def test_wildcard_source(self, router):
        calls = []
        router.register("*", "push", lambda e: calls.append(1) or True)
        await router.receive("any_source", "push", {})
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_wildcard_event_type(self, router):
        calls = []
        router.register("github", "*", lambda e: calls.append(1) or True)
        await router.receive("github", "anything", {})
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_pending_events_empty(self, router):
        assert router.pending_events() == []

    @pytest.mark.asyncio
    async def test_pending_events_unprocessed(self, router):
        await router.receive("src", "type", {})
        pending = router.pending_events()
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_processed_not_in_pending(self, router):
        router.register("src", "type", lambda e: True)
        await router.receive("src", "type", {})
        assert router.pending_events() == []

    @pytest.mark.asyncio
    async def test_event_history(self, router):
        await router.receive("a", "b", {})
        await router.receive("c", "d", {})
        history = router.event_history()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_event_history_limit(self, router):
        for i in range(10):
            await router.receive("s", "t", {"i": i})
        history = router.event_history(limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_stats(self, router):
        await router.receive("s", "t", {})
        s = router.stats()
        assert s["total"] == 1
        assert "processed" in s
        assert "failed" in s

    @pytest.mark.asyncio
    async def test_handler_exception_counted_as_failed(self, router):
        def bad_handler(evt):
            raise RuntimeError("oops")

        router.register("s", "t", bad_handler)
        await router.receive("s", "t", {})
        assert router.stats()["failed"] == 1

    @pytest.mark.asyncio
    async def test_no_match_does_not_process(self, router):
        router.register("github", "push", lambda e: True)
        event = await router.receive("gitlab", "merge", {})
        assert event.processed is False
