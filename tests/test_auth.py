"""Tests for sovereign/api/auth.py — JWT creation, verification, revocation, rate-limit."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from sovereign.api.auth import (
    check_rate_limit,
    create_token,
    is_revoked,
    reset_rate_limit,
    revoke_token,
    verify_token,
)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

class TestCreateToken:
    def test_returns_three_part_jwt(self):
        token = create_token({"sub": "alice"})
        assert len(token.split(".")) == 3

    def test_payload_round_trips(self):
        token = create_token({"sub": "bob", "role": "admin"})
        payload = verify_token(token)
        assert payload["sub"] == "bob"
        assert payload["role"] == "admin"

    def test_token_includes_iat_exp_jti(self):
        token = create_token({"sub": "x"})
        payload = verify_token(token)
        assert "iat" in payload
        assert "exp" in payload
        assert "jti" in payload

    def test_default_expiry_is_8h(self):
        before = int(time.time())
        token = create_token({"sub": "x"})
        payload = verify_token(token)
        assert payload["exp"] - payload["iat"] == pytest.approx(28_800, abs=2)

    def test_custom_expiry(self):
        token = create_token({"sub": "x"}, exp_seconds=60)
        payload = verify_token(token)
        assert payload["exp"] - payload["iat"] == pytest.approx(60, abs=2)

    def test_each_token_has_unique_jti(self):
        t1 = create_token({"sub": "x"})
        t2 = create_token({"sub": "x"})
        assert verify_token(t1)["jti"] != verify_token(t2)["jti"]


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

class TestVerifyToken:
    def test_valid_token_returns_payload(self):
        token = create_token({"sub": "alice"})
        payload = verify_token(token)
        assert payload["sub"] == "alice"

    def test_tampered_signature_raises(self):
        token = create_token({"sub": "alice"})
        parts = token.split(".")
        parts[2] = parts[2][:-4] + "XXXX"
        with pytest.raises(ValueError, match="Invalid signature"):
            verify_token(".".join(parts))

    def test_wrong_number_of_parts_raises(self):
        with pytest.raises(ValueError, match="Invalid token format"):
            verify_token("only.two")

    def test_expired_token_raises(self):
        token = create_token({"sub": "x"}, exp_seconds=-1)
        with pytest.raises(ValueError, match="expired"):
            verify_token(token)

    def test_completely_invalid_string_raises(self):
        with pytest.raises(ValueError):
            verify_token("not-a-token")

    def test_revoked_token_raises(self):
        token = create_token({"sub": "x"})
        payload = verify_token(token)
        revoke_token(payload["jti"], float(payload["exp"]))
        with pytest.raises(ValueError, match="revoked"):
            verify_token(token)


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------

class TestTokenRevocation:
    def test_is_revoked_false_for_new_token(self):
        token = create_token({"sub": "x"})
        jti = verify_token(token)["jti"]
        assert not is_revoked(jti)

    def test_is_revoked_true_after_revoke(self):
        token = create_token({"sub": "x"})
        payload = verify_token(token)
        revoke_token(payload["jti"], float(payload["exp"]))
        assert is_revoked(payload["jti"])

    def test_expired_revocation_is_pruned(self):
        jti = "test-jti-prune"
        revoke_token(jti, time.time() - 1)  # already expired
        # After prune the jti is gone
        assert not is_revoked(jti)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_first_attempts_allowed(self):
        reset_rate_limit("10.0.0.1")
        for _ in range(5):
            assert check_rate_limit("10.0.0.1")

    def test_exceeding_limit_returns_false(self):
        reset_rate_limit("10.0.0.2")
        for _ in range(10):
            check_rate_limit("10.0.0.2")  # fill up
        assert not check_rate_limit("10.0.0.2")

    def test_reset_clears_attempts(self):
        reset_rate_limit("10.0.0.3")
        for _ in range(10):
            check_rate_limit("10.0.0.3")
        assert not check_rate_limit("10.0.0.3")
        reset_rate_limit("10.0.0.3")
        assert check_rate_limit("10.0.0.3")

    def test_different_ips_are_independent(self):
        reset_rate_limit("192.168.1.1")
        reset_rate_limit("192.168.1.2")
        for _ in range(10):
            check_rate_limit("192.168.1.1")
        assert not check_rate_limit("192.168.1.1")
        assert check_rate_limit("192.168.1.2")


# ---------------------------------------------------------------------------
# Production startup check
# ---------------------------------------------------------------------------

class TestProductionStartup:
    def test_no_key_in_production_raises(self, monkeypatch):
        monkeypatch.setenv("SOVEREIGN_ENV", "production")
        monkeypatch.delenv("AUTH_SECRET_KEY", raising=False)
        from sovereign.api.auth import assert_production_ready
        with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
            assert_production_ready()

    def test_key_present_in_production_ok(self, monkeypatch):
        monkeypatch.setenv("SOVEREIGN_ENV", "production")
        monkeypatch.setenv("AUTH_SECRET_KEY", "a" * 64)
        from sovereign.api.auth import assert_production_ready
        assert_production_ready()  # should not raise

    def test_no_key_in_dev_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("SOVEREIGN_ENV", "development")
        monkeypatch.delenv("AUTH_SECRET_KEY", raising=False)
        from sovereign.api.auth import assert_production_ready
        assert_production_ready()  # dev: warn only, no raise
