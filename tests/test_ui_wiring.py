"""Tests for UI wiring: mode management, API routes, WS handler, dashboard HTML."""
from __future__ import annotations

import pathlib

_SRC = pathlib.Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Orchestrator mode management
# ---------------------------------------------------------------------------

class TestOrchestratorModes:
    def test_set_mode_via_source(self):
        src = (_SRC / "sovereign" / "orchestrator.py").read_text()
        assert "set_mode" in src
        assert "_VALID_MODES" in src

    def test_valid_modes_in_source(self):
        src = (_SRC / "sovereign" / "orchestrator.py").read_text()
        for mode in ("command", "business", "personal", "finance", "study",
                     "travel", "research", "builder", "local_offline", "survival"):
            assert mode in src

    def test_current_mode_property_in_source(self):
        src = (_SRC / "sovereign" / "orchestrator.py").read_text()
        assert "current_mode" in src

    def test_emit_mode_changed(self):
        src = (_SRC / "sovereign" / "orchestrator.py").read_text()
        assert "mode_changed" in src

    def test_sovereign_orchestrator_class_name(self):
        src = (_SRC / "sovereign" / "orchestrator.py").read_text()
        assert "class SovereignOrchestrator" in src

    def test_set_mode_returns_false_for_invalid(self):
        from unittest.mock import MagicMock
        from sovereign.orchestrator import SovereignOrchestrator
        orch = MagicMock()
        orch.config = MagicMock()
        orch._event_callbacks = []
        orch._VALID_MODES = SovereignOrchestrator._VALID_MODES
        result = SovereignOrchestrator.set_mode(orch, "nonexistent_mode")
        assert result is False

    def test_set_mode_returns_true_for_valid(self):
        from unittest.mock import MagicMock
        from sovereign.orchestrator import SovereignOrchestrator
        orch = MagicMock()
        orch.config = MagicMock()
        orch._event_callbacks = []
        orch._VALID_MODES = SovereignOrchestrator._VALID_MODES
        result = SovereignOrchestrator.set_mode(orch, "finance")
        assert result is True

    def test_valid_modes_count(self):
        from sovereign.orchestrator import SovereignOrchestrator
        assert len(SovereignOrchestrator._VALID_MODES) == 10


# ---------------------------------------------------------------------------
# API routes in server.py
# ---------------------------------------------------------------------------

class TestServerRoutes:
    def _src(self):
        return (_SRC / "sovereign" / "api" / "server.py").read_text()

    def test_memory_domain_route_exists(self):
        assert "/api/memory/{domain}" in self._src()

    def test_get_mode_route_exists(self):
        assert "/api/mode" in self._src()

    def test_set_mode_route_exists(self):
        src = self._src()
        assert "set_mode" in src
        assert "SetModeRequest" in src

    def test_entities_panel_route(self):
        assert "/entities" in self._src()

    def test_api_entities_route(self):
        assert "/api/entities" in self._src()

    def test_api_entities_sync_route(self):
        assert "/api/entities/{entity_id}/sync" in self._src()

    def test_memory_route_requires_auth(self):
        src = self._src()
        assert "require_auth" in src
        assert "/api/memory/{domain}" in src

    def test_provision_entity_requires_auth(self):
        src = self._src()
        assert "provision_entity" in src

    def test_deprovision_route_exists(self):
        assert "deprovision_entity" in self._src()


# ---------------------------------------------------------------------------
# WS handler — mode_change dispatch
# ---------------------------------------------------------------------------

class TestWSHandlerDispatch:
    def _src(self):
        return (_SRC / "sovereign" / "api" / "ws_handler.py").read_text()

    def test_mode_change_handled(self):
        assert "mode_change" in self._src()

    def test_mode_changed_response(self):
        assert "mode_changed" in self._src()

    def test_cancel_handled(self):
        assert "cancel" in self._src()

    def test_set_mode_called(self):
        assert "set_mode" in self._src()

    def test_current_mode_referenced(self):
        assert "current_mode" in self._src()


# ---------------------------------------------------------------------------
# Executive dashboard — mobile-responsive HTML
# ---------------------------------------------------------------------------

class TestExecutiveDashboard:
    def _html(self):
        return (_SRC / "sovereign" / "api" / "templates" / "executive_dashboard.html").read_text()

    def test_has_viewport_meta(self):
        assert 'name="viewport"' in self._html()

    def test_has_mobile_web_app_capable(self):
        assert "mobile-web-app-capable" in self._html()

    def test_has_manifest_link(self):
        assert 'rel="manifest"' in self._html()

    def test_has_responsive_grid(self):
        html = self._html()
        assert "grid-cols-1" in html or "lg:grid-cols" in html

    def test_has_bottom_nav_mobile_only(self):
        assert "md:hidden" in self._html()

    def test_has_kpi_cards(self):
        assert "kpis" in self._html()

    def test_has_goals_section(self):
        assert "goals" in self._html()

    def test_has_projects_section(self):
        assert "projects" in self._html()

    def test_has_agent_activity(self):
        assert "agent" in self._html().lower()

    def test_has_add_goal_modal(self):
        assert "addGoalModal" in self._html()

    def test_fetches_live_goals(self):
        assert "/api/goals" in self._html()

    def test_fetches_live_projects(self):
        assert "/api/projects" in self._html()

    def test_has_mode_fetch(self):
        assert "/api/mode" in self._html()


# ---------------------------------------------------------------------------
# index.html — Pro Chat UI features
# ---------------------------------------------------------------------------

class TestIndexHTML:
    def _html(self):
        return (_SRC / "sovereign" / "api" / "templates" / "index.html").read_text()

    def test_has_service_worker_registration(self):
        assert "serviceWorker" in self._html()

    def test_has_manifest_link(self):
        assert 'rel="manifest"' in self._html()

    def test_has_mobile_meta(self):
        assert "mobile-web-app-capable" in self._html()

    def test_has_websocket(self):
        html = self._html()
        assert "WebSocket" in html or "ws://" in html or "wss://" in html

    def test_has_stream_handling(self):
        html = self._html()
        assert "stream_delta" in html or "stream" in html

    def test_has_chat_input(self):
        html = self._html()
        assert "textarea" in html.lower() or 'type="text"' in html


# ---------------------------------------------------------------------------
# Entities system
# ---------------------------------------------------------------------------

class TestEntitiesWiring:
    def test_entity_registry_importable(self):
        from sovereign.entities.entity_registry import EntityRegistry
        assert callable(EntityRegistry)

    def test_vault_manager_importable(self):
        from sovereign.entities.vault_manager import EntityVault
        assert callable(EntityVault)

    def test_provisioner_importable(self):
        from sovereign.entities.provisioner import EntityProvisioner
        assert callable(EntityProvisioner)

    def test_orchestrator_has_entity_provisioner_property(self):
        src = (_SRC / "sovereign" / "orchestrator.py").read_text()
        assert "entity_provisioner" in src
        assert "_init_entities" in src

    def test_server_has_entities_panel(self):
        src = (_SRC / "sovereign" / "api" / "server.py").read_text()
        assert "entities_panel" in src
        assert "entities_panel.html" in src
