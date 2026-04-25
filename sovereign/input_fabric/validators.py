"""Input validators — check inputs before processing."""
from __future__ import annotations

from typing import Any


def validate_input_type(input_type: str) -> None:
    VALID = ("text", "pdf", "json", "csv", "image", "audio", "unknown")
    if input_type not in VALID:
        raise ValueError(f"Unknown input_type '{input_type}'. Valid: {VALID}")


def validate_not_empty(raw: Any) -> None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise ValueError("Input must not be empty.")
