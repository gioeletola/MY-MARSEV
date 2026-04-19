"""Tests for sovereign/security/secret_manager.py."""
from __future__ import annotations

import pytest


class TestSecretManager:
    @pytest.fixture
    def manager(self, tmp_path):
        from sovereign.security.secret_manager import SecretManager
        return SecretManager(store_path=tmp_path / "secrets.json")

    def test_set_and_get(self, manager):
        manager.set("api_key", "supersecret")
        val = manager.get("api_key")
        assert val == "supersecret"

    def test_get_nonexistent(self, manager):
        assert manager.get("ghost") is None

    def test_delete_existing(self, manager):
        manager.set("to_delete", "value")
        ok = manager.delete("to_delete")
        assert ok is True
        assert manager.get("to_delete") is None

    def test_delete_nonexistent(self, manager):
        ok = manager.delete("nonexistent")
        assert ok is False

    def test_rotate_secret(self, manager):
        manager.set("key", "old_value")
        ok = manager.rotate("key", "new_value")
        assert ok is True
        assert manager.get("key") == "new_value"

    def test_rotate_nonexistent(self, manager):
        ok = manager.rotate("ghost", "new")
        assert ok is False

    def test_list_names(self, manager):
        manager.set("a", "v1")
        manager.set("b", "v2")
        names = manager.list_names()
        assert "a" in names
        assert "b" in names

    def test_list_names_empty(self, manager):
        assert manager.list_names() == []

    def test_expired_secrets(self, manager):
        manager.set("expired_key", "val", expires_at="2020-01-01T00:00:00+00:00")
        expired = manager.expired()
        assert "expired_key" in expired

    def test_not_expired_secrets(self, manager):
        manager.set("future_key", "val", expires_at="2099-01-01T00:00:00+00:00")
        expired = manager.expired()
        assert "future_key" not in expired

    def test_persistence(self, tmp_path):
        from sovereign.security.secret_manager import SecretManager
        path = tmp_path / "secrets.json"
        m1 = SecretManager(store_path=path)
        m1.set("persistent", "value123")
        m2 = SecretManager(store_path=path)
        assert m2.get("persistent") == "value123"

    def test_overwrite_existing(self, manager):
        manager.set("key", "v1")
        manager.set("key", "v2")
        assert manager.get("key") == "v2"

    def test_category_stored(self, manager):
        entry = manager.set("token", "abc", category="api_keys")
        assert entry.category == "api_keys"

    def test_value_not_stored_plaintext(self, manager, tmp_path):
        import json
        manager.set("password", "mysecretpassword")
        data = json.loads((tmp_path / "secrets.json").read_text())
        raw_value = data["password"]["value"]
        assert "mysecretpassword" not in raw_value

    def test_secret_id_stable_on_overwrite(self, manager):
        entry1 = manager.set("stable", "v1")
        entry2 = manager.set("stable", "v2")
        assert entry1.secret_id == entry2.secret_id


class TestXorCipher:
    def test_encrypt_decrypt_roundtrip(self):
        from sovereign.security.secret_manager import _encrypt, _decrypt
        original = "my secret value"
        assert _decrypt(_encrypt(original)) == original

    def test_different_inputs_different_cipher(self):
        from sovereign.security.secret_manager import _encrypt
        c1 = _encrypt("hello")
        c2 = _encrypt("world")
        assert c1 != c2

    def test_empty_string(self):
        from sovereign.security.secret_manager import _encrypt, _decrypt
        assert _decrypt(_encrypt("")) == ""

    def test_derive_key_fallback(self):
        from sovereign.security.secret_manager import _derive_key, _FALLBACK_KEY
        import os
        old = os.environ.pop("SECRET_MANAGER_KEY", None)
        try:
            key = _derive_key()
            assert key == _FALLBACK_KEY
        finally:
            if old is not None:
                os.environ["SECRET_MANAGER_KEY"] = old
