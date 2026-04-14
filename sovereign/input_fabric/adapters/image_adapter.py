"""
Image adapter — stub for image-to-text extraction.

For Claude's vision capability, pass the image as a base64-encoded
content block directly in the messages list rather than through this pipeline.
This adapter handles OCR fallback for non-Claude paths.
"""
from __future__ import annotations
from typing import Any


class ImageAdapter:
    async def extract(self, raw: Any) -> str:
        # Stub: return a placeholder
        return (
            "[Image input detected. "
            "Pass images directly as base64 content blocks to Claude for vision tasks.]"
        )
