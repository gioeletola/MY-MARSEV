"""
PDF adapter — extracts text from PDF bytes.

Requires the 'pdf' optional dependency: pip install sovereign-ai-os[pdf]
which installs pymupdf.
"""
from __future__ import annotations
from typing import Any


class PdfAdapter:
    async def extract(self, raw: Any) -> str:
        try:
            import fitz  # pymupdf
            doc = fitz.open(stream=raw, filetype="pdf")
            pages = [page.get_text() for page in doc]
            return "\n\n".join(pages)
        except ImportError:
            return (
                "[PDF adapter requires pymupdf: pip install sovereign-ai-os[pdf]]\n"
                + str(raw)[:500]
            )
        except Exception as exc:
            return f"[PDF extraction failed: {exc}]"
