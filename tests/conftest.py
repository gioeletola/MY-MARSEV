"""
Global pytest configuration.

Sets a deterministic AUTH_SECRET_KEY so that auth tests can create and
verify tokens without requiring the variable to be present in the shell
environment.  Production enforcement is tested separately via monkeypatch.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _set_auth_secret_key(monkeypatch):
    """Ensure AUTH_SECRET_KEY is always set during tests (64-char hex string)."""
    if not os.environ.get("AUTH_SECRET_KEY"):
        monkeypatch.setenv(
            "AUTH_SECRET_KEY",
            "a" * 64,  # deterministic test key — never used in production
        )
