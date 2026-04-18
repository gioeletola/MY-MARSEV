"""
Tests for the full expansion pipeline:
  APISpecParser, ConnectorBuilder, AgentPromoter, SelfExpansionPolicy, AgentTester.
"""
from __future__ import annotations

import json
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OPENAPI3_MINIMAL = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.2.3"},
    "servers": [{"url": "https://api.example.com/v1"}],
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer"}
        }
    },
    "security": [{"bearerAuth": []}],
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "summary": "List all items",
                "parameters": [],
                "responses": {"200": {}},
                "security": [{"bearerAuth": []}],
            },
            "post": {
                "operationId": "createItem",
                "summary": "Create an item",
                "requestBody": {"content": {"application/json": {"schema": {}}}},
                "responses": {"201": {}},
            },
        },
        "/items/{id}": {
            "get": {
                "operationId": "getItem",
                "summary": "Get item by ID",
                "parameters": [{"name": "id", "in": "path"}],
                "responses": {"200": {}},
            },
        },
    },
}

_SWAGGER2_MINIMAL = {
    "swagger": "2.0",
    "info": {"title": "Pet Store", "version": "1.0"},
    "host": "petstore.example.com",
    "basePath": "/api",
    "schemes": ["https"],
    "securityDefinitions": {
        "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    },
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [],
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
}

_APIKEY_OPENAPI3 = {
    "openapi": "3.0.0",
    "info": {"title": "Key API", "version": "0.1"},
    "components": {
        "securitySchemes": {
            "apiKeyHeader": {"type": "apiKey", "in": "header", "name": "X-Custom-Key"}
        }
    },
    "paths": {},
}


# ---------------------------------------------------------------------------
# TestAPISpecParser
# ---------------------------------------------------------------------------

class TestAPISpecParser:
    def _parser(self):
        from sovereign.expansion.api_spec_parser import APISpecParser
        return APISpecParser()

    def test_parse_openapi3_returns_blueprint(self):
        bp = self._parser().parse(_OPENAPI3_MINIMAL)
        assert bp.title == "Test API"
        assert bp.version == "1.2.3"
        assert bp.base_url == "https://api.example.com/v1"

    def test_parse_openapi3_endpoint_count(self):
        bp = self._parser().parse(_OPENAPI3_MINIMAL)
        assert len(bp.endpoints) == 3

    def test_parse_openapi3_endpoint_methods(self):
        bp = self._parser().parse(_OPENAPI3_MINIMAL)
        methods = {ep.method for ep in bp.endpoints}
        assert "GET" in methods
        assert "POST" in methods

    def test_parse_openapi3_operation_ids(self):
        bp = self._parser().parse(_OPENAPI3_MINIMAL)
        op_ids = {ep.operation_id for ep in bp.endpoints}
        assert "listItems" in op_ids
        assert "createItem" in op_ids
        assert "getItem" in op_ids

    def test_parse_swagger2(self):
        bp = self._parser().parse(_SWAGGER2_MINIMAL)
        assert bp.title == "Pet Store"
        assert "petstore.example.com" in bp.base_url
        assert len(bp.endpoints) == 1
        assert bp.endpoints[0].operation_id == "listPets"

    def test_detect_bearer_auth(self):
        bp = self._parser().parse(_OPENAPI3_MINIMAL)
        assert bp.auth_type == "bearer"
        assert bp.auth_header == "Authorization"

    def test_detect_apikey_auth_openapi3(self):
        bp = self._parser().parse(_APIKEY_OPENAPI3)
        assert bp.auth_type == "apikey"
        assert bp.auth_header == "X-Custom-Key"

    def test_detect_apikey_auth_swagger2(self):
        bp = self._parser().parse(_SWAGGER2_MINIMAL)
        assert bp.auth_type == "apikey"
        assert bp.auth_header == "X-API-Key"

    def test_unrecognised_spec_raises(self):
        with pytest.raises(ValueError, match="Unrecognised"):
            self._parser().parse({"not_a_spec": True})

    def test_parse_json_string(self):
        from sovereign.expansion.api_spec_parser import APISpecParser
        parser = APISpecParser()
        bp = parser.parse_json(json.dumps(_SWAGGER2_MINIMAL))
        assert bp.title == "Pet Store"

    def test_servers_list_populated(self):
        bp = self._parser().parse(_OPENAPI3_MINIMAL)
        assert "https://api.example.com/v1" in bp.servers


# ---------------------------------------------------------------------------
# TestConnectorBuilder
# ---------------------------------------------------------------------------

class TestConnectorBuilder:
    def _builder(self, tmp_path):
        from sovereign.expansion.connector_builder import ConnectorBuilder
        return ConnectorBuilder(output_dir=str(tmp_path / "generated"))

    def _blueprint(self):
        from sovereign.expansion.api_spec_parser import APISpecParser
        return APISpecParser().parse(_OPENAPI3_MINIMAL)

    def test_generate_code_returns_string(self, tmp_path):
        code = self._builder(tmp_path).generate_code(self._blueprint())
        assert isinstance(code, str)
        assert len(code) > 50

    def test_class_name_in_code(self, tmp_path):
        code = self._builder(tmp_path).generate_code(self._blueprint())
        assert "TestApiIntegration" in code or "Integration" in code

    def test_base_url_in_code(self, tmp_path):
        code = self._builder(tmp_path).generate_code(self._blueprint())
        assert "api.example.com" in code

    def test_method_names_in_code(self, tmp_path):
        code = self._builder(tmp_path).generate_code(self._blueprint())
        assert "list_items" in code or "listItems" in code or "get_item" in code

    def test_build_writes_file(self, tmp_path):
        builder = self._builder(tmp_path)
        builder.build(self._blueprint(), write=True)
        gen_dir = tmp_path / "generated"
        files = list(gen_dir.glob("*.py"))
        assert len(files) >= 1

    def test_build_returns_valid_python(self, tmp_path):
        import ast
        code = self._builder(tmp_path).generate_code(self._blueprint())
        # Should be syntactically valid Python
        ast.parse(code)


# ---------------------------------------------------------------------------
# TestAgentPromoter
# ---------------------------------------------------------------------------

class TestAgentPromoter:
    def _promoter(self, tmp_path, monkeypatch):
        from sovereign.expansion import agent_promoter as mod
        monkeypatch.setattr(mod, "_LEDGER_PATH", tmp_path / "ledger.json")
        from sovereign.expansion.agent_promoter import AgentPromoter
        return AgentPromoter(min_shadow_calls=3)  # low threshold for tests

    def test_register_agent(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        lc = p.register("agent_alpha", "AlphaClass", "research")
        assert lc.agent_id == "agent_alpha"
        assert lc.domain == "research"

    def test_register_idempotent(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        p.register("agent_beta", "BetaClass", "content")
        p.register("agent_beta", "BetaClass", "content")
        # Should still be only one lifecycle entry
        assert len([k for k in p._lifecycles if k == "agent_beta"]) == 1

    def test_try_promote_sandbox_to_shadow_pass(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        p.register("agent_good", "GoodClass", "research")
        ok, reason = p.try_promote("agent_good", test_pass_rate=0.90, promoted_by="auto")
        assert ok is True, reason
        from sovereign.expansion.agent_promoter import AgentStage
        assert p.get("agent_good").current_stage == AgentStage.SHADOW

    def test_try_promote_sandbox_to_shadow_fail_low_pass_rate(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        p.register("agent_weak", "WeakClass", "research")
        ok, reason = p.try_promote("agent_weak", test_pass_rate=0.50, promoted_by="auto")
        assert ok is False
        assert "Pass rate" in reason or "pass rate" in reason.lower()

    def test_try_promote_shadow_to_prod_fails_needs_more_shadow_calls(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        p.register("agent_new_shadow", "NewShadow", "research")
        # Promote to shadow first
        p.try_promote("agent_new_shadow", test_pass_rate=0.90, promoted_by="auto")
        # Now try prod without enough shadow calls
        ok, reason = p.try_promote("agent_new_shadow", test_pass_rate=0.95, promoted_by="human_jane")
        assert ok is False
        assert "shadow calls" in reason.lower() or "shadow" in reason.lower()

    def test_retire_agent(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        p.register("agent_old", "OldClass", "content")
        ok = p.retire("agent_old", by="admin")
        assert ok is True
        from sovereign.expansion.agent_promoter import AgentStage
        assert p.get("agent_old").current_stage == AgentStage.RETIRED

    def test_retire_unknown_agent_returns_false(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        assert p.retire("ghost") is False

    def test_snapshot_returns_list(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        p.register("ag1", "C1", "d1")
        p.register("ag2", "C2", "d2")
        snap = p.snapshot()
        assert isinstance(snap, list)
        assert len(snap) == 2
        assert all("agent_id" in s and "stage" in s for s in snap)

    def test_list_by_stage(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        from sovereign.expansion.agent_promoter import AgentStage
        p.register("s_agent", "SC", "research")
        p.try_promote("s_agent", test_pass_rate=0.9, promoted_by="auto")
        shadow_list = p.list_by_stage(AgentStage.SHADOW)
        assert any(lc.agent_id == "s_agent" for lc in shadow_list)

    def test_record_shadow_comparison(self, tmp_path, monkeypatch):
        p = self._promoter(tmp_path, monkeypatch)
        p.register("shadow_tester", "STC", "research")
        p.try_promote("shadow_tester", test_pass_rate=0.9, promoted_by="auto")
        p.record_shadow_comparison("shadow_tester", agreed=True)
        p.record_shadow_comparison("shadow_tester", agreed=False)
        lc = p.get("shadow_tester")
        assert lc.shadow_comparisons == 2
        assert lc.shadow_agreements == 1


# ---------------------------------------------------------------------------
# TestSelfExpansionPolicy
# ---------------------------------------------------------------------------

class TestSelfExpansionPolicy:
    def _policy(self):
        from sovereign.expansion.self_expansion_policy import SelfExpansionPolicy
        return SelfExpansionPolicy()

    def test_financial_domain_blocks_auto(self):
        """Financial domain always requires human approval."""
        from sovereign.expansion.agent_promoter import AgentStage
        policy = self._policy()
        ok, reason = policy.check_promotion(
            agent_id="fin_agent", domain="financial",
            from_stage=AgentStage.SANDBOX, promoted_by="auto"
        )
        assert ok is False
        assert "high-risk" in reason.lower() or "requires human" in reason.lower()

    def test_financial_domain_allows_human_promotion(self):
        """Financial domain allows promotion when promoted by a human."""
        from sovereign.expansion.agent_promoter import AgentStage
        policy = self._policy()
        # Disable the shadow→prod human-only flag for this test
        policy.set_require_human_for_production(False)
        ok, reason = policy.check_promotion(
            agent_id="fin_agent2", domain="financial",
            from_stage=AgentStage.SANDBOX, promoted_by="jane_cfo"
        )
        assert ok is True, reason

    def test_locked_agent_blocks(self):
        """Permanently locked agents cannot be promoted."""
        from sovereign.expansion.agent_promoter import AgentStage
        policy = self._policy()
        ok, reason = policy.check_promotion(
            agent_id="ceo_agent", domain="executive",
            from_stage=AgentStage.SANDBOX, promoted_by="human_admin"
        )
        assert ok is False
        assert "locked" in reason.lower() or "permanently" in reason.lower()

    def test_custom_rule_blocks(self):
        """A custom rule returning False blocks promotion."""
        from sovereign.expansion.agent_promoter import AgentStage
        policy = self._policy()

        def my_block_rule(**kwargs):
            return False, "blocked by custom rule"

        policy.add_rule("test_block", my_block_rule)
        ok, reason = policy.check_promotion(
            agent_id="safe_agent", domain="content",
            from_stage=AgentStage.SANDBOX, promoted_by="auto"
        )
        assert ok is False
        assert "blocked by custom rule" in reason

    def test_shadow_to_prod_requires_human_by_default(self):
        """By default, shadow→prod promotion requires human sign-off."""
        from sovereign.expansion.agent_promoter import AgentStage
        policy = self._policy()
        ok, reason = policy.check_promotion(
            agent_id="ordinary_agent", domain="content",
            from_stage=AgentStage.SHADOW, promoted_by="auto"
        )
        assert ok is False

    def test_add_blocked_domain(self):
        """A custom blocked domain is enforced as high-risk."""
        from sovereign.expansion.agent_promoter import AgentStage
        policy = self._policy()
        policy.add_blocked_domain("experimental")
        ok, reason = policy.check_promotion(
            agent_id="exp_agent", domain="experimental",
            from_stage=AgentStage.SANDBOX, promoted_by="auto"
        )
        assert ok is False

    def test_summary_shape(self):
        policy = self._policy()
        s = policy.summary()
        assert "high_risk_domains" in s
        assert "locked_agents" in s
        assert "financial" in s["high_risk_domains"]
        assert "ceo_agent" in s["locked_agents"]


# ---------------------------------------------------------------------------
# TestAgentTester
# ---------------------------------------------------------------------------

class TestAgentTester:
    def _tester(self):
        from sovereign.expansion.agent_tester import AgentTester
        # All dependencies can be None for unit-testing build_default_suite
        return AgentTester(
            claude_client=None,
            tool_registry=None,
            memory_manager=None,
            constitution=None,
            prompt_builder=None,
        )

    def test_build_default_suite_returns_suite(self):
        from sovereign.expansion.agent_tester import AgentTestSuite
        tester = self._tester()
        suite = tester.build_default_suite("my_agent", object)
        assert isinstance(suite, AgentTestSuite)
        assert suite.agent_id == "my_agent"

    def test_build_default_suite_has_at_least_2_cases(self):
        tester = self._tester()
        suite = tester.build_default_suite("test_agent", object)
        assert len(suite.cases) >= 2

    def test_default_suite_has_smoke_test(self):
        tester = self._tester()
        suite = tester.build_default_suite("test_agent", object)
        ids = [c.test_id for c in suite.cases]
        assert "smoke" in ids

    def test_default_suite_has_safety_refusal(self):
        tester = self._tester()
        suite = tester.build_default_suite("test_agent", object)
        ids = [c.test_id for c in suite.cases]
        assert "safety_refusal" in ids

    def test_suite_pass_rate_zero_with_no_results(self):
        tester = self._tester()
        suite = tester.build_default_suite("test_agent", object)
        assert suite.pass_rate == 0.0

    def test_suite_passed_failed_counts_zero(self):
        tester = self._tester()
        suite = tester.build_default_suite("test_agent", object)
        assert suite.passed == 0
        assert suite.failed == 0
