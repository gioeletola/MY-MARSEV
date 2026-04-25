"""
Image adapter — converts image inputs to Claude vision content blocks or OCR text.

Priority:
  1. If a ClaudeClient is available, emit a base64 content block for vision.
  2. If pytesseract is installed (local OCR fallback), extract text.
  3. Return an informative placeholder.

Input `raw` may be:
  - str: file path or data URI (data:image/...;base64,...)
  - bytes: raw image bytes
  - dict: already-formed {"type": "image", "source": {...}} block
"""
from __future__ import annotations

import base64
import pathlib
from typing import Any

_PLACEHOLDER = (
    "[Image received — pass directly as a vision content block to Claude, "
    "or install pytesseract for local OCR fallback.]"
)


class ImageAdapter:
    """Converts image inputs to text or Claude vision content blocks."""

    async def extract(self, raw: Any) -> str:
        if isinstance(raw, dict) and raw.get("type") == "image":
            # Already a Claude content block — signal caller to use it directly
            return f"[Vision block: {raw.get('source', {}).get('media_type', 'image')}]"

        img_bytes = await self._to_bytes(raw)
        if img_bytes is None:
            return _PLACEHOLDER

        # Try pytesseract OCR first (no API call needed)
        ocr_text = self._try_ocr(img_bytes)
        if ocr_text:
            return ocr_text

        # Return a Claude-compatible description hint with base64 payload
        b64 = base64.b64encode(img_bytes).decode()
        media_type = self._guess_media_type(img_bytes)
        return (
            f"[Image ({media_type}, {len(img_bytes)} bytes). "
            f"To analyze with Claude vision, use content block: "
            f'{{"type":"image","source":{{"type":"base64","media_type":"{media_type}",'
            f'"data":"{b64[:32]}..."}}}}'
            f"]"
        )

    async def to_claude_block(self, raw: Any) -> dict[str, Any] | None:
        """Return a Claude API vision content block, or None if conversion fails."""
        img_bytes = await self._to_bytes(raw)
        if img_bytes is None:
            return None
        media_type = self._guess_media_type(img_bytes)
        b64 = base64.b64encode(img_bytes).decode()
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64,
            },
        }

    async def _to_bytes(self, raw: Any) -> bytes | None:
        if isinstance(raw, bytes):
            return raw
        if isinstance(raw, str):
            if raw.startswith("data:"):
                # data URI
                try:
                    header, data = raw.split(",", 1)
                    return base64.b64decode(data)
                except Exception:
                    return None
            # File path
            path = pathlib.Path(raw)
            if path.exists():
                return path.read_bytes()
        return None

    def _try_ocr(self, img_bytes: bytes) -> str:
        try:
            import io
            import pytesseract  # type: ignore[import]
            from PIL import Image  # type: ignore[import]
            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img).strip()
            return text or ""
        except ImportError:
            return ""
        except Exception:
            return ""

    def _guess_media_type(self, img_bytes: bytes) -> str:
        if img_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if img_bytes[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if img_bytes[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        if img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"
