"""
Core type definitions for the SOVEREIGN Skills Runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillStatus(str, Enum):
    ACTIVE = "active"
    BETA = "beta"
    SHADOW = "shadow"
    STUB = "stub"
    DISABLED = "disabled"


class SkillPermission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    FILES = "files"
    CODE = "code"
    APPROVAL_REQUIRED = "approval_required"


@dataclass
class SkillInput:
    name: str
    type: str           # "string" | "integer" | "boolean" | "file" | "list"
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class SkillOutput:
    name: str
    type: str
    description: str = ""


@dataclass
class SkillDependency:
    skill_id: str
    optional: bool = False


@dataclass
class SkillDefinition:
    """Parsed representation of a skill .toml file."""
    skill_id: str
    name: str
    description: str
    version: str = "1.0.0"
    status: SkillStatus = SkillStatus.ACTIVE
    permissions: list[SkillPermission] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)           # tool_ids required
    agents: list[str] = field(default_factory=list)          # agent_ids this skill may invoke
    inputs: list[SkillInput] = field(default_factory=list)
    outputs: list[SkillOutput] = field(default_factory=list)
    dependencies: list[SkillDependency] = field(default_factory=list)
    prompt_template: str = ""
    tags: list[str] = field(default_factory=list)
    author: str = "system"
    requires_approval: bool = False
    source_file: str = ""

    # Runtime-populated
    enabled: bool = True


@dataclass
class SkillExecutionResult:
    skill_id: str
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    tokens_used: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    requires_human_review: bool = False
