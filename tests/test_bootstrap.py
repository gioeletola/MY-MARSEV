"""
Tests for sovereign/bootstrap.py — SovereignConfig and create_orchestrator.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ===========================================================================
# SovereignConfig tests
# ===========================================================================

class TestSovereignConfig:
    """Tests for the SovereignConfig Pydantic model."""

    def test_minimal_config(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(api_key="test-key")
        assert cfg.api_key == "test-key"
        assert cfg.default_operating_mode == "command"
        assert cfg.default_model == "claude-sonnet-4-6"
        assert cfg.log_level == "INFO"
        assert cfg.json_logs is False
        assert cfg.enable_streaming is True

    def test_custom_values(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(
            api_key="sk-test",
            default_operating_mode="finance",
            max_action_class="EXECUTE",
            approval_mode="auto",
            log_level="DEBUG",
            json_logs=True,
        )
        assert cfg.default_operating_mode == "finance"
        assert cfg.max_action_class == "EXECUTE"
        assert cfg.approval_mode == "auto"
        assert cfg.log_level == "DEBUG"
        assert cfg.json_logs is True

    def test_max_action_class_uppercased(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(api_key="k", max_action_class="suggest")
        assert cfg.max_action_class == "SUGGEST"

    def test_max_action_class_invalid_raises(self):
        from sovereign.bootstrap import SovereignConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SovereignConfig(api_key="k", max_action_class="INVALID")

    def test_approval_mode_invalid_raises(self):
        from sovereign.bootstrap import SovereignConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SovereignConfig(api_key="k", approval_mode="manual")

    def test_approval_mode_auto_valid(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(api_key="k", approval_mode="auto")
        assert cfg.approval_mode == "auto"

    def test_approval_mode_cli_valid(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(api_key="k", approval_mode="cli")
        assert cfg.approval_mode == "cli"

    def test_all_valid_action_classes(self):
        from sovereign.bootstrap import SovereignConfig

        for cls in ("READ", "SUGGEST", "DRAFT", "EXECUTE"):
            cfg = SovereignConfig(api_key="k", max_action_class=cls)
            assert cfg.max_action_class == cls

    def test_data_dir_default(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(api_key="k")
        assert cfg.data_dir == "data"

    def test_prompts_dir_default(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(api_key="k")
        assert cfg.prompts_dir == "prompts"


# ===========================================================================
# SovereignConfig.from_env_and_file tests
# ===========================================================================

class TestSovereignConfigFromEnvAndFile:
    def test_loads_from_yaml_file(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import SovereignConfig

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        cfg_file = tmp_path / "sovereign.yaml"
        cfg_file.write_text("default_operating_mode: finance\nlog_level: DEBUG\n")
        cfg = SovereignConfig.from_env_and_file(str(cfg_file))
        assert cfg.default_operating_mode == "finance"
        assert cfg.log_level == "DEBUG"
        assert cfg.api_key == "env-key"

    def test_missing_api_key_raises(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import SovereignConfig

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("DOTENV_PATH", raising=False)
        # Create a config file without an api_key
        cfg_file = tmp_path / "sovereign.yaml"
        cfg_file.write_text("default_operating_mode: command\n")
        # Patch load_dotenv to be a no-op so it doesn't pick up a real .env
        with patch("sovereign.bootstrap.load_dotenv"):
            with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
                SovereignConfig.from_env_and_file(str(cfg_file))

    def test_env_overrides_yaml(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import SovereignConfig

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        monkeypatch.setenv("SOVEREIGN_LOG_LEVEL", "WARNING")
        cfg_file = tmp_path / "sovereign.yaml"
        cfg_file.write_text("log_level: INFO\n")
        cfg = SovereignConfig.from_env_and_file(str(cfg_file))
        assert cfg.log_level == "WARNING"

    def test_missing_yaml_file_uses_defaults(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import SovereignConfig

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        nonexistent = tmp_path / "nonexistent.yaml"
        cfg = SovereignConfig.from_env_and_file(str(nonexistent))
        assert cfg.api_key == "env-key"
        assert cfg.default_operating_mode == "command"

    def test_sovereign_data_dir_env_override(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import SovereignConfig

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        monkeypatch.setenv("SOVEREIGN_DATA_DIR", "/custom/data")
        cfg = SovereignConfig.from_env_and_file(str(tmp_path / "no.yaml"))
        assert cfg.data_dir == "/custom/data"

    def test_sovereign_approval_mode_env_override(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import SovereignConfig

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        monkeypatch.setenv("SOVEREIGN_APPROVAL_MODE", "auto")
        cfg = SovereignConfig.from_env_and_file(str(tmp_path / "no.yaml"))
        assert cfg.approval_mode == "auto"

    def test_sovereign_default_model_env_override(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import SovereignConfig

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        monkeypatch.setenv("SOVEREIGN_DEFAULT_MODEL", "claude-haiku-4-5")
        cfg = SovereignConfig.from_env_and_file(str(tmp_path / "no.yaml"))
        assert cfg.default_model == "claude-haiku-4-5"

    def test_empty_yaml_file_uses_defaults(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import SovereignConfig

        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        cfg_file = tmp_path / "empty.yaml"
        cfg_file.write_text("")
        cfg = SovereignConfig.from_env_and_file(str(cfg_file))
        assert cfg.api_key == "env-key"
        assert cfg.default_operating_mode == "command"


# ===========================================================================
# create_orchestrator tests
# ===========================================================================

class TestCreateOrchestrator:
    def test_returns_orchestrator_instance(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import create_orchestrator
        from sovereign.orchestrator import SovereignOrchestrator

        monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key-for-ci")
        cfg_file = tmp_path / "sovereign.yaml"
        cfg_file.write_text("")

        # Patch __init__ to skip the complex initialization chain
        with patch.object(SovereignOrchestrator, "__init__", lambda self, cfg: setattr(self, "config", cfg)):
            orch = create_orchestrator(str(cfg_file))
            assert orch is not None
            assert isinstance(orch, SovereignOrchestrator)

    def test_orchestrator_has_config(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import create_orchestrator
        from sovereign.orchestrator import SovereignOrchestrator

        monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key-for-ci")
        cfg_file = tmp_path / "sovereign.yaml"
        cfg_file.write_text("default_operating_mode: business\n")

        with patch.object(SovereignOrchestrator, "__init__", lambda self, cfg: setattr(self, "config", cfg)):
            orch = create_orchestrator(str(cfg_file))
            assert orch.config.default_operating_mode == "business"
            assert orch.config.api_key == "dummy-key-for-ci"

    def test_create_orchestrator_configures_logging(self, tmp_path, monkeypatch):
        from sovereign.bootstrap import create_orchestrator
        from sovereign.orchestrator import SovereignOrchestrator

        monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key-for-ci")

        with patch.object(SovereignOrchestrator, "__init__", lambda self, cfg: setattr(self, "config", cfg)), \
             patch("sovereign.observability.structured_logger.configure_logging") as mock_log:
            create_orchestrator(str(tmp_path / "no.yaml"))
            mock_log.assert_called_once()

    def test_re_exported_sovereign_orchestrator(self):
        """Ensure bootstrap re-exports SovereignOrchestrator."""
        import sovereign.bootstrap as bs
        from sovereign.orchestrator import SovereignOrchestrator

        assert hasattr(bs, "SovereignOrchestrator")
        assert bs.SovereignOrchestrator is SovereignOrchestrator


# ===========================================================================
# SovereignConfig field defaults / edge cases
# ===========================================================================

class TestSovereignConfigEdgeCases:
    def test_api_key_required(self):
        from sovereign.bootstrap import SovereignConfig
        from pydantic import ValidationError

        with pytest.raises((ValidationError, TypeError)):
            SovereignConfig()  # missing api_key

    def test_config_is_pydantic_model(self):
        from sovereign.bootstrap import SovereignConfig
        from pydantic import BaseModel

        assert issubclass(SovereignConfig, BaseModel)

    def test_serialise_to_dict(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(api_key="k")
        d = cfg.model_dump()
        assert isinstance(d, dict)
        assert d["api_key"] == "k"

    def test_max_action_class_case_insensitive_read(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(api_key="k", max_action_class="read")
        assert cfg.max_action_class == "READ"

    def test_max_action_class_case_insensitive_draft(self):
        from sovereign.bootstrap import SovereignConfig

        cfg = SovereignConfig(api_key="k", max_action_class="draft")
        assert cfg.max_action_class == "DRAFT"
