"""
Bootstrap — loads configuration and wires up the SovereignOrchestrator.

Entry point for all deployment contexts:
  from sovereign.bootstrap import create_orchestrator
  orch = create_orchestrator()
  result = await orch.handle_request("...")
"""
from __future__ import annotations

import os
import pathlib
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class SovereignConfig(BaseModel):
    """
    Validated runtime configuration.

    Loaded from config/sovereign.yaml first, then environment variables
    override individual keys. ANTHROPIC_API_KEY is always required from env.
    """

    api_key: str = Field(..., description="Anthropic API key (ANTHROPIC_API_KEY)")
    data_dir: str = "data"
    prompts_dir: str = "prompts"
    log_level: str = "INFO"
    json_logs: bool = False
    default_model: str = "claude-sonnet-4-6"
    default_operating_mode: str = "command"
    max_action_class: str = "SUGGEST"
    approval_mode: str = "cli"
    enable_streaming: bool = True

    @field_validator("max_action_class")
    @classmethod
    def validate_action_class(cls, v: str) -> str:
        valid = ("READ", "SUGGEST", "DRAFT", "EXECUTE")
        if v.upper() not in valid:
            raise ValueError(f"max_action_class must be one of {valid}, got '{v}'")
        return v.upper()

    @field_validator("approval_mode")
    @classmethod
    def validate_approval_mode(cls, v: str) -> str:
        if v not in ("cli", "auto"):
            raise ValueError(f"approval_mode must be 'cli' or 'auto', got '{v}'")
        return v

    @classmethod
    def from_env_and_file(
        cls,
        config_path: str = "config/sovereign.yaml",
    ) -> "SovereignConfig":
        """
        Load config: YAML file → overlay env vars → validate.

        Required env var: ANTHROPIC_API_KEY
        Optional env overrides: SOVEREIGN_LOG_LEVEL, SOVEREIGN_DATA_DIR,
                                SOVEREIGN_APPROVAL_MODE, SOVEREIGN_DEFAULT_MODEL
        """
        load_dotenv()

        data: dict[str, Any] = {}
        p = pathlib.Path(config_path)
        if p.exists():
            with p.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        # Environment variable overrides
        env_map = {
            "SOVEREIGN_LOG_LEVEL":      "log_level",
            "SOVEREIGN_DATA_DIR":       "data_dir",
            "SOVEREIGN_APPROVAL_MODE":  "approval_mode",
            "SOVEREIGN_DEFAULT_MODEL":  "default_model",
            "SOVEREIGN_MAX_ACTION_CLASS": "max_action_class",
        }
        for env_key, config_key in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                data[config_key] = val

        # Required: API key
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Add it to your .env file or export it in your shell."
            )
        data["api_key"] = api_key

        return cls(**data)


def create_orchestrator(
    config_path: str = "config/sovereign.yaml",
) -> "SovereignOrchestrator":
    """
    Top-level factory function.

    1. Load and validate SovereignConfig
    2. Configure structured logging
    3. Instantiate and return SovereignOrchestrator

    This is the only function most callers need.
    """
    from sovereign.observability.structured_logger import configure_logging
    from sovereign.orchestrator import SovereignOrchestrator

    config = SovereignConfig.from_env_and_file(config_path)
    configure_logging(config.log_level, config.json_logs)
    return SovereignOrchestrator(config)


# Re-export for convenience
from sovereign.orchestrator import SovereignOrchestrator  # noqa: E402
