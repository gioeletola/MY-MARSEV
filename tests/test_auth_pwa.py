"""Tests for JWT auth module and PWA assets."""
from __future__ import annotations

import time
import pytest


# ---------------------------------------------------------------------------
# JWT auth unit tests
# ---------------------------------------------------------------------------

class TestJWTAuth:
    def _mod(self):
        from sovereign.api import auth
        return auth

    def test_create_token_returns_three_parts(self):
        m = self._mod()
        token = m.create_token({"sub": "admin"})
        assert token.count(".") == 2

    def test_verify_valid_token(self):
        m = self._mod()
        token = m.create_token({"sub": "alice", "role": "admin"})
        payload = m.verify_token(token)
        assert payload["sub"] == "alice"
        assert payload["role"] == "admin"

    def test_verify_includes_exp_and_iat(self):
        m = self._mod()
        token = m.create_token({"sub": "test"})
        payload = m.verify_token(token)
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > time.time()

    def test_tampered_signature_raises(self):
        m = self._mod()
        token = m.create_token({"sub": "admin"})
        parts = token.split(".")
        parts[2] = "invalidsignature"
        bad = ".".join(parts)
        with pytest.raises(ValueError, match="Invalid signature"):
            m.verify_token(bad)

    def test_tampered_payload_raises(self):
        import base64
        import json
        m = self._mod()
        token = m.create_token({"sub": "user"})
        header, body, sig = token.split(".")
        # Craft evil payload
        evil = base64.urlsafe_b64encode(
            json.dumps({"sub": "admin", "role": "superadmin"}).encode()
        ).rstrip(b"=").decode()
        bad = f"{header}.{evil}.{sig}"
        with pytest.raises(ValueError):
            m.verify_token(bad)

    def test_expired_token_raises(self):
        m = self._mod()
        token = m.create_token({"sub": "test"}, exp_seconds=-1)
        with pytest.raises(ValueError, match="expired"):
            m.verify_token(token)

    def test_invalid_format_raises(self):
        m = self._mod()
        with pytest.raises(ValueError, match="Invalid token format"):
            m.verify_token("not.a.jwt.at.all")

    def test_wrong_secret_raises(self, monkeypatch):
        m = self._mod()
        token = m.create_token({"sub": "admin"})
        monkeypatch.setenv("AUTH_SECRET_KEY", "wrong-secret")
        with pytest.raises(ValueError):
            m.verify_token(token)


# ---------------------------------------------------------------------------
# PWA assets
# ---------------------------------------------------------------------------

class TestPWAAssets:
    def _static(self):
        import pathlib
        return pathlib.Path(__file__).parent.parent / "sovereign" / "api" / "static"

    def test_manifest_exists(self):
        assert (self._static() / "manifest.json").exists()

    def test_sw_exists(self):
        assert (self._static() / "sw.js").exists()

    def test_manifest_valid_json(self):
        import json
        data = json.loads((self._static() / "manifest.json").read_text())
        assert data["name"] == "SOVEREIGN AI OS"
        assert data["display"] == "standalone"
        assert "icons" in data

    def test_manifest_has_shortcuts(self):
        import json
        data = json.loads((self._static() / "manifest.json").read_text())
        assert len(data.get("shortcuts", [])) >= 1

    def test_sw_has_cache_name(self):
        code = (self._static() / "sw.js").read_text()
        assert "sovereign-v1" in code
        assert "install" in code
        assert "activate" in code
        assert "fetch" in code

    def test_sw_skips_api_routes(self):
        code = (self._static() / "sw.js").read_text()
        assert "/api/" in code

    def test_index_html_has_manifest_link(self):
        import pathlib
        html = (
            pathlib.Path(__file__).parent.parent
            / "sovereign" / "api" / "templates" / "index.html"
        ).read_text()
        assert 'rel="manifest"' in html
        assert "/manifest.json" in html

    def test_index_html_has_mobile_web_app_capable(self):
        import pathlib
        html = (
            pathlib.Path(__file__).parent.parent
            / "sovereign" / "api" / "templates" / "index.html"
        ).read_text()
        assert "mobile-web-app-capable" in html

    def test_index_html_has_theme_color(self):
        import pathlib
        html = (
            pathlib.Path(__file__).parent.parent
            / "sovereign" / "api" / "templates" / "index.html"
        ).read_text()
        assert "theme-color" in html

    def test_index_html_registers_sw(self):
        import pathlib
        html = (
            pathlib.Path(__file__).parent.parent
            / "sovereign" / "api" / "templates" / "index.html"
        ).read_text()
        assert "serviceWorker" in html


# ---------------------------------------------------------------------------
# Auth module — server route protection (import-level check)
# ---------------------------------------------------------------------------

class TestServerAuthWiring:
    def test_require_auth_importable(self):
        from sovereign.api.auth import require_auth
        assert callable(require_auth)

    def test_server_imports_auth(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "sovereign" / "api" / "server.py"
        assert "require_auth" in src.read_text()

    def test_server_protects_budget_route(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "sovereign" / "api" / "server.py"
        text = src.read_text()
        assert "require_auth" in text
        assert "/api/budget" in text

    def test_server_has_login_route(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "sovereign" / "api" / "server.py"
        assert "/api/auth/login" in src.read_text()

    def test_server_has_public_status_route(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "sovereign" / "api" / "server.py"
        assert "/api/status" in src.read_text()

    def test_server_serves_manifest(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "sovereign" / "api" / "server.py"
        assert "/manifest.json" in src.read_text()

    def test_server_serves_sw(self):
        import pathlib
        src = pathlib.Path(__file__).parent.parent / "sovereign" / "api" / "server.py"
        assert "/sw.js" in src.read_text()
