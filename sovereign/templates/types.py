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


class TemplateCategory(str, Enum):
    """High-level categories for template organisation."""
    SYSTEM = "system"
    AGENT = "agent"
    REPORT = "report"
    EMAIL = "email"
    DECISION = "decision"
    NOTIFICATION = "notification"
    ONBOARDING = "onboarding"


@dataclass
class TemplateEntry:
    """
    A content template supporting {{variable}} substitution.

    Fields:
        template_id     — unique identifier
        name            — human-readable label
        category        — TemplateCategory value
        content         — the template body with {{variable}} placeholders
        required_vars   — vars that must be present in render context
        optional_vars   — vars that may be absent (rendered as empty string if missing)
        version         — semantic version string
        author          — who created this template
    """
    template_id: str
    name: str
    category: TemplateCategory
    content: str
    required_vars: list[str] = field(default_factory=list)
    optional_vars: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = "system"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    status: TemplateStatus = TemplateStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemplateDefinition:
    """A persona/template preset that configures an agent's behavior (legacy type)."""
    template_id: str
    name: str
    description: str
    version: str = "1.0.0"
    status: TemplateStatus = TemplateStatus.ACTIVE
    system_prompt: str = ""
    preferred_model: str = "claude-sonnet-4-6"
    preferred_tools: list[str] = field(default_factory=list)
    max_tokens: int = 2048
    temperature_hint: float = 0.7
    tags: list[str] = field(default_factory=list)
    author: str = "system"
    output_format: str = "markdown"
    source_file: str = ""
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
