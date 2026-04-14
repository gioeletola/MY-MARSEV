"""
Streaming helpers for the SOVEREIGN AI OS.

Utilities for consuming and displaying streamed Claude API responses.
"""
from __future__ import annotations

import sys
from typing import AsyncIterator


async def stream_to_stdout(
    chunks: AsyncIterator[str],
    end: str = "\n",
    flush: bool = True,
) -> str:
    """
    Consume a text-delta stream, print each chunk, and return the full text.

    Args:
        chunks: Async iterator of text delta strings (from ClaudeClient.stream).
        end:    String appended after the stream completes.
        flush:  Whether to flush stdout after each chunk.

    Returns:
        The complete assembled text.
    """
    parts: list[str] = []
    async for chunk in chunks:
        print(chunk, end="", flush=flush, file=sys.stdout)
        parts.append(chunk)
    print(end, end="", flush=flush)
    return "".join(parts)


async def collect_stream(chunks: AsyncIterator[str]) -> str:
    """
    Silently consume a text-delta stream and return the full assembled text.
    """
    parts: list[str] = []
    async for chunk in chunks:
        parts.append(chunk)
    return "".join(parts)
