"""Memory domain: project. Extend this stub with domain-specific record schemas."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProjectRecord:
    """A record in the project memory domain."""
    id: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    tags: list[str] = field(default_factory=list)


DOMAIN_NAME = "project"
