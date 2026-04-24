"""Template/persona type definitions."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TemplateStatus(str, Enum):
    ACTIVE = "active"
    BETA = "beta"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


@dataclass
class TemplateDefinition:
    """A persona/template preset that configures an agent's behavior."""
    template_id: str
    name: str
    description: str
    version: str = "1.0.0"
    status: TemplateStatus = TemplateStatus.ACTIVE
    system_prompt: str = ""
    preferred_model: str = "claude-sonnet-4-6"
    preferred_tools: list[str] = field(default_factory=list)
    max_tokens: int = 2048
    temperature_hint: float = 0.7       # 0.0=deterministic, 1.0=creative
    tags: list[str] = field(default_factory=list)
    author: str = "system"
    output_format: str = "markdown"     # "markdown" | "json" | "plain"
    source_file: str = ""
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
