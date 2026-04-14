"""Text normalisation utilities used by the pipeline."""
from __future__ import annotations
import re


def collapse_whitespace(text: str) -> str:
    """Replace runs of whitespace with a single space (preserves newlines)."""
    lines = text.splitlines()
    return "\n".join(" ".join(line.split()) for line in lines)


def remove_null_bytes(text: str) -> str:
    return text.replace("\x00", "")


def truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Truncate text to max_chars. Returns (truncated_text, was_truncated)."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True
