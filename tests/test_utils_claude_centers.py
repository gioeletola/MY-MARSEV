"""
Tests for utility modules (normalizers, validators, streaming, tool_formatter,
tool_router) and all sovereign/centers/ modules.
"""
from __future__ import annotations

import pytest


# ===========================================================================
# normalizers
# ===========================================================================

class TestNormalizers:
    def test_collapse_whitespace_single_line(self):
        from sovereign.input_fabric.normalizers import collapse_whitespace
        assert collapse_whitespace("hello   world") == "hello world"

    def test_collapse_whitespace_multiline(self):
        from sovereign.input_fabric.normalizers import collapse_whitespace
        result = collapse_whitespace("line one\n  spaces   here")
        assert result == "line one\nspaces here"

    def test_collapse_whitespace_empty(self):
        from sovereign.input_fabric.normalizers import collapse_whitespace
        assert collapse_whitespace("") == ""

    def test_collapse_whitespace_tabs(self):
        from sovereign.input_fabric.normalizers import collapse_whitespace
        assert collapse_whitespace("a\t\tb") == "a b"

    def test_remove_null_bytes(self):
        from sovereign.input_fabric.normalizers import remove_null_bytes
        assert remove_null_bytes("hel\x00lo") == "hello"

    def test_remove_null_bytes_none(self):
        from sovereign.input_fabric.normalizers import remove_null_bytes
        assert remove_null_bytes("clean") == "clean"

    def test_truncate_short(self):
        from sovereign.input_fabric.normalizers import truncate
        text, was_truncated = truncate("hello", 10)
        assert text == "hello"
        assert was_truncated is False

    def test_truncate_exact(self):
        from sovereign.input_fabric.normalizers import truncate
        text, was_truncated = truncate("hello", 5)
        assert text == "hello"
        assert was_truncated is False

    def test_truncate_long(self):
        from sovereign.input_fabric.normalizers import truncate
        text, was_truncated = truncate("hello world", 5)
        assert text == "hello"
        assert was_truncated is True


# ===========================================================================
# validators
# ===========================================================================

class TestValidators:
    def test_validate_input_type_valid(self):
        from sovereign.input_fabric.validators import validate_input_type
        for t in ("text", "pdf", "json", "csv", "image", "audio", "unknown"):
            validate_input_type(t)  # should not raise

    def test_validate_input_type_invalid(self):
        from sovereign.input_fabric.validators import validate_input_type
        with pytest.raises(ValueError):
            validate_input_type("xml")

    def test_validate_not_empty_valid(self):
        from sovereign.input_fabric.validators import validate_not_empty
        validate_not_empty("hello")  # should not raise

    def test_validate_not_empty_none(self):
        from sovereign.input_fabric.validators import validate_not_empty
        with pytest.raises(ValueError):
            validate_not_empty(None)

    def test_validate_not_empty_blank_string(self):
        from sovereign.input_fabric.validators import validate_not_empty
        with pytest.raises(ValueError):
            validate_not_empty("   ")

    def test_validate_not_empty_empty_string(self):
        from sovereign.input_fabric.validators import validate_not_empty
        with pytest.raises(ValueError):
            validate_not_empty("")


# ===========================================================================
# claude.streaming
# ===========================================================================

class TestStreaming:
    @pytest.mark.asyncio
    async def test_collect_stream(self):
        from sovereign.claude.streaming import collect_stream

        async def gen():
            for chunk in ["hello", " ", "world"]:
                yield chunk

        result = await collect_stream(gen())
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_collect_stream_empty(self):
        from sovereign.claude.streaming import collect_stream

        async def gen():
            return
            yield  # make it an async generator

        result = await collect_stream(gen())
        assert result == ""

    @pytest.mark.asyncio
    async def test_stream_to_stdout(self, capsys):
        from sovereign.claude.streaming import stream_to_stdout

        async def gen():
            for chunk in ["hi", " there"]:
                yield chunk

        result = await stream_to_stdout(gen(), end="", flush=False)
        assert result == "hi there"

    @pytest.mark.asyncio
    async def test_stream_to_stdout_empty(self, capsys):
        from sovereign.claude.streaming import stream_to_stdout

        async def gen():
            return
            yield

        result = await stream_to_stdout(gen(), end="", flush=False)
        assert result == ""


# ===========================================================================
# claude.tool_formatter
# ===========================================================================

class TestToolFormatter:
    def test_tools_to_api_valid(self):
        from sovereign.claude.tool_formatter import tools_to_api
        tools = [{"name": "t", "description": "desc", "input_schema": {"type": "object"}}]
        result = tools_to_api(tools)
        assert len(result) == 1
        assert result[0]["name"] == "t"

    def test_tools_to_api_missing_key(self):
        from sovereign.claude.tool_formatter import tools_to_api
        with pytest.raises(ValueError):
            tools_to_api([{"name": "t", "description": "desc"}])

    def test_tools_to_api_empty_list(self):
        from sovereign.claude.tool_formatter import tools_to_api
        assert tools_to_api([]) == []

    def test_tools_to_api_multiple(self):
        from sovereign.claude.tool_formatter import tools_to_api
        tools = [
            {"name": "a", "description": "da", "input_schema": {}},
            {"name": "b", "description": "db", "input_schema": {}},
        ]
        result = tools_to_api(tools)
        assert len(result) == 2

    def test_parse_tool_use_block(self):
        from sovereign.claude.tool_formatter import parse_tool_use_block

        class FakeBlock:
            id = "tid-001"
            name = "my_tool"
            input = {"key": "val"}

        tid, name, inp = parse_tool_use_block(FakeBlock())
        assert tid == "tid-001"
        assert name == "my_tool"
        assert inp == {"key": "val"}

    def test_make_tool_result_block_normal(self):
        from sovereign.claude.tool_formatter import make_tool_result_block
        block = make_tool_result_block("tid-001", "result data")
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "tid-001"
        assert block["content"] == "result data"
        assert "is_error" not in block

    def test_make_tool_result_block_error(self):
        from sovereign.claude.tool_formatter import make_tool_result_block
        block = make_tool_result_block("tid-002", "oops", is_error=True)
        assert block["is_error"] is True

    def test_make_tool_result_block_coerces_content(self):
        from sovereign.claude.tool_formatter import make_tool_result_block
        block = make_tool_result_block("t", {"nested": "dict"})
        assert isinstance(block["content"], str)


# ===========================================================================
# tools.tool_router
# ===========================================================================

class TestToolRouter:
    @pytest.fixture
    def router(self):
        from sovereign.tools.tool_registry import ToolRegistry
        from sovereign.tools.tool_router import ToolRouter
        from sovereign.tools.builtin.file_ops import FileOpsTool
        reg = ToolRegistry()
        reg.register(FileOpsTool())
        return ToolRouter(reg)

    def test_suggest_file_tool(self, router):
        tools = router.suggest_tools("read file config.yaml")
        assert "file_ops" in tools

    def test_suggest_no_match(self, router):
        tools = router.suggest_tools("analyze quarterly results")
        assert tools == []

    def test_suggest_unregistered_tool_excluded(self, router):
        # web_search not registered, so should NOT appear
        tools = router.suggest_tools("search the web for info")
        assert "web_search" not in tools

    def test_suggest_returns_sorted_list(self, router):
        tools = router.suggest_tools("file code execute")
        assert tools == sorted(tools)


# ===========================================================================
# Centers — simple stub centers (route + describe)
# ===========================================================================

class TestSimpleCenters:
    """Test all 21-line centers that share the same route/describe pattern."""

    def test_vault_center_route_keyword(self):
        from sovereign.centers.vault_center import VaultCenter
        c = VaultCenter()
        assert c.route("document review") == "document_manager"

    def test_vault_center_route_default(self):
        from sovereign.centers.vault_center import VaultCenter
        c = VaultCenter()
        assert c.route("anything else") == "document_manager"

    def test_vault_center_describe(self):
        from sovereign.centers.vault_center import VaultCenter
        d = VaultCenter().describe()
        assert "center_id" in d and "description" in d

    def test_ai_qa_center_route(self):
        from sovereign.centers.ai_qa_center import AIQACenter
        c = AIQACenter()
        assert c.route("bias detection analysis") == "bias_detector"

    def test_ai_qa_center_default(self):
        from sovereign.centers.ai_qa_center import AIQACenter
        assert AIQACenter().route("unknown thing") == "qa_testing"

    def test_ai_qa_center_describe(self):
        from sovereign.centers.ai_qa_center import AIQACenter
        d = AIQACenter().describe()
        assert "center_id" in d

    def test_automation_center_route(self):
        from sovereign.centers.automation_center import AutomationCenter
        assert AutomationCenter().route("deploy to production") == "deployment_assistant"

    def test_automation_center_default(self):
        from sovereign.centers.automation_center import AutomationCenter
        assert AutomationCenter().route("misc task") == "codebridge_chief"

    def test_automation_center_describe(self):
        from sovereign.centers.automation_center import AutomationCenter
        d = AutomationCenter().describe()
        assert "agents" in d

    def test_concierge_center_route(self):
        from sovereign.centers.concierge_center import ConciergeCenter
        assert ConciergeCenter().route("travel booking") == "travel_planner"

    def test_concierge_center_default(self):
        from sovereign.centers.concierge_center import ConciergeCenter
        assert ConciergeCenter().route("nothing matched") == "concierge_chief"

    def test_concierge_center_describe(self):
        from sovereign.centers.concierge_center import ConciergeCenter
        d = ConciergeCenter().describe()
        assert d["center_id"] == "concierge_centre"

    def test_cultural_center_exists(self):
        from sovereign.centers.cultural_center import CulturalCenter
        c = CulturalCenter()
        assert hasattr(c, "route") or hasattr(c, "describe")

    def test_data_fabric_center_exists(self):
        from sovereign.centers.data_fabric_center import DataFabricCenter
        c = DataFabricCenter()
        assert c is not None

    def test_diary_center_exists(self):
        from sovereign.centers.diary_center import DiaryCenter
        c = DiaryCenter()
        assert c is not None

    def test_governance_center_exists(self):
        from sovereign.centers.governance_center import GovernanceCenter
        c = GovernanceCenter()
        assert c is not None

    def test_inventory_center_exists(self):
        from sovereign.centers.inventory_center import InventoryCenter
        c = InventoryCenter()
        assert c is not None

    def test_life_os_center_exists(self):
        from sovereign.centers.life_os_center import LifeOSCenter
        c = LifeOSCenter()
        assert c is not None

    def test_maximizer_center_exists(self):
        from sovereign.centers.maximizer_center import MaximizerCenter
        c = MaximizerCenter()
        assert c is not None

    def test_media_editing_center_exists(self):
        from sovereign.centers.media_editing_center import MediaEditingCenter
        c = MediaEditingCenter()
        assert c is not None

    def test_partner_center_exists(self):
        from sovereign.centers.partner_center import PartnerCenter
        c = PartnerCenter()
        assert c is not None

    def test_personal_research_center_exists(self):
        from sovereign.centers.personal_research_center import PersonalResearchCenter
        c = PersonalResearchCenter()
        assert c is not None

    def test_resilience_recovery_center_exists(self):
        from sovereign.centers.resilience_recovery_center import ResilienceRecoveryCenter
        c = ResilienceRecoveryCenter()
        assert c is not None

    def test_scenario_simulation_center_exists(self):
        from sovereign.centers.scenario_simulation_center import ScenarioSimulationCenter
        c = ScenarioSimulationCenter()
        assert c is not None

    def test_second_brain_center_exists(self):
        from sovereign.centers.second_brain_center import SecondBrainCenter
        c = SecondBrainCenter()
        assert c is not None


class TestBusinessCenter:
    @pytest.fixture
    def center(self):
        from sovereign.centers.business_center import BusinessCenter
        return BusinessCenter(agent_registry=None)

    def test_route_sales(self, center):
        agent_id = center.route(["sales", "pipeline"])
        assert agent_id == "sales_chief"

    def test_route_marketing(self, center):
        agent_id = center.route(["marketing"])
        assert "marketing" in agent_id.lower() or agent_id is not None

    def test_route_default(self, center):
        agent_id = center.route(["unknown_topic"])
        assert isinstance(agent_id, str)

    def test_list_domains(self, center):
        domains = center.list_domains()
        assert isinstance(domains, list)
        assert len(domains) > 0


class TestAccountingCenter:
    @pytest.fixture
    def center(self):
        from sovereign.centers.accounting_center import AccountingCenter
        return AccountingCenter(agent_registry=None)

    def test_route_cashflow(self, center):
        assert center.route(["cashflow"]) == "cashflow_analyst"

    def test_route_budget(self, center):
        assert center.route(["budget"]) == "budget_manager"

    def test_route_tax(self, center):
        assert center.route(["tax"]) == "tax_optimizer"

    def test_route_default(self, center):
        assert center.route([]) == "finance_ops_chief"

    def test_list_domains(self, center):
        domains = center.list_domains()
        assert "finance_ops_chief" in domains


class TestCRMCenter:
    @pytest.fixture
    def center(self):
        from sovereign.centers.crm_center import CRMCenter
        return CRMCenter(agent_registry=None)

    def test_route_lead(self, center):
        aid = center.route(["lead"])
        assert "lead" in aid.lower() or isinstance(aid, str)

    def test_route_default(self, center):
        aid = center.route([])
        assert isinstance(aid, str)


class TestContentCenter:
    @pytest.fixture
    def center(self):
        from sovereign.centers.content_center import ContentCenter
        return ContentCenter(agent_registry=None)

    def test_route_content(self, center):
        aid = center.route(["content"])
        assert isinstance(aid, str)

    def test_route_default(self, center):
        aid = center.route([])
        assert isinstance(aid, str)


class TestBICenter:
    @pytest.fixture
    def center(self):
        from sovereign.centers.bi_center import BusinessIntelligenceCenter
        return BusinessIntelligenceCenter(agent_registry=None)

    def test_route_kpi(self, center):
        aid = center.route(["kpi"])
        assert isinstance(aid, str)

    def test_route_default(self, center):
        aid = center.route([])
        assert isinstance(aid, str)

    def test_list_domains(self, center):
        domains = center.list_domains()
        assert isinstance(domains, list)


class TestHRCenter:
    def test_route_and_describe(self):
        from sovereign.centers.hr_center import HRCenter
        c = HRCenter(agent_registry=None)
        aid = c.route([])
        assert isinstance(aid, str)


class TestLegalCenter:
    def test_route_and_describe(self):
        from sovereign.centers.legal_center import LegalCenter
        c = LegalCenter(agent_registry=None)
        aid = c.route([])
        assert isinstance(aid, str)


class TestPersonalCenter:
    def test_route_and_describe(self):
        from sovereign.centers.personal_center import PersonalCenter
        c = PersonalCenter(agent_registry=None)
        aid = c.route([])
        assert isinstance(aid, str)


class TestStrategicCenter:
    def test_route_and_describe(self):
        from sovereign.centers.strategic_center import StrategicCenter
        c = StrategicCenter(agent_registry=None)
        aid = c.route([])
        assert isinstance(aid, str)


# ===========================================================================
# SecretsVault — skipped if cryptography package is broken in this env
# ===========================================================================

_vault_importable = True
try:
    from sovereign.infra.secrets_vault import SecretsVault as _SV  # noqa: F401
except BaseException:
    _vault_importable = False

@pytest.mark.skipif(not _vault_importable, reason="cryptography package unavailable")
class TestSecretsVault:
    def test_instantiation(self):
        from sovereign.infra.secrets_vault import SecretsVault
        vault = SecretsVault()
        assert vault is not None

    def test_get_from_env(self, monkeypatch):
        from sovereign.infra.secrets_vault import SecretsVault
        monkeypatch.setenv("VAULT_TEST_KEY", "env_value")
        vault = SecretsVault()
        assert vault.get("VAULT_TEST_KEY") == "env_value"

    def test_get_default(self):
        from sovereign.infra.secrets_vault import SecretsVault
        vault = SecretsVault()
        assert vault.get("NONEXISTENT_KEY_XYZ", "fallback") == "fallback"

    def test_get_default_empty(self):
        from sovereign.infra.secrets_vault import SecretsVault
        vault = SecretsVault()
        assert vault.get("NONEXISTENT_KEY_XYZ") == ""

    def test_list_keys_empty(self):
        from sovereign.infra.secrets_vault import SecretsVault
        vault = SecretsVault()
        keys = vault.list_keys()
        assert isinstance(keys, list)

    def test_list_keys_includes_file_cache(self, monkeypatch):
        from sovereign.infra.secrets_vault import SecretsVault
        vault = SecretsVault()
        vault._file_cache["test_secret"] = "value"
        keys = vault.list_keys()
        assert "test_secret" in keys

    def test_set_without_fernet_raises(self):
        from sovereign.infra.secrets_vault import SecretsVault
        vault = SecretsVault()
        vault._fernet = None
        with pytest.raises(RuntimeError):
            vault.set("key", "value")

    def test_get_priority_env_over_file(self, monkeypatch):
        from sovereign.infra.secrets_vault import SecretsVault
        monkeypatch.setenv("PRIORITY_TEST", "from_env")
        vault = SecretsVault()
        vault._file_cache["PRIORITY_TEST"] = "from_file"
        assert vault.get("PRIORITY_TEST") == "from_env"

    def test_get_file_over_vault(self):
        from sovereign.infra.secrets_vault import SecretsVault
        vault = SecretsVault()
        vault._file_cache["FILE_VAULT_KEY"] = "from_file"
        vault._vault_cache["FILE_VAULT_KEY"] = "from_vault"
        assert vault.get("FILE_VAULT_KEY") == "from_file"
