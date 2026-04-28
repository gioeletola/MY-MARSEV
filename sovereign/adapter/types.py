"""Adapter type contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class AdapterFormat(str, Enum):
    JSON      = "json"
    CSV       = "csv"
    XML       = "xml"
    MARKDOWN  = "markdown"
    HTML      = "html"
    YAML      = "yaml"
    BINARY    = "binary"
    TEXT      = "text"
    TABLE     = "table"


@dataclass
class AdapterResult:
    success: bool
    data: Any
    adapter_id: str = ""
    from_format: str = ""
    to_format: str = ""
    duration_ms: float = 0.0
    error: str = ""
