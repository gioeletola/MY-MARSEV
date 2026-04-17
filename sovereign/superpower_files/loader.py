"""Superpower loader — loads and injects knowledge packs into agent prompts."""
from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PACK_NAMES = [
    "negotiation", "fundraising", "product", "growth",
    "legal_basics", "mental_models", "financial_iq", "leadership",
]


class SuperpowerLoader:
    """
    Loads knowledge packs and provides them as formatted text blocks
    ready for injection into system prompts.
    """

    def __init__(self) -> None:
        self._packs: dict[str, dict[str, Any]] = {}
        self._load_all()

    def _load_all(self) -> None:
        for name in _PACK_NAMES:
            try:
                mod = importlib.import_module(f"sovereign.superpower_files.{name}")
                self._packs[name] = getattr(mod, "PACK", {})
            except ImportError as exc:
                logger.warning("Superpower pack %s not found: %s", name, exc)

    def get(self, pack_name: str) -> dict[str, Any] | None:
        return self._packs.get(pack_name)

    def render(self, pack_name: str) -> str:
        pack = self._packs.get(pack_name)
        if not pack:
            return ""
        lines = [f"=== SUPERPOWER: {pack.get('title', pack_name).upper()} ===", ""]
        for section, content in pack.get("sections", {}).items():
            lines.append(f"## {section}")
            if isinstance(content, list):
                for item in content:
                    lines.append(f"- {item}")
            elif isinstance(content, dict):
                for k, v in content.items():
                    lines.append(f"• {k}: {v}")
            else:
                lines.append(str(content))
            lines.append("")
        return "\n".join(lines)

    def inject(self, pack_names: list[str], base_prompt: str) -> str:
        blocks = [self.render(n) for n in pack_names if n in self._packs]
        if not blocks:
            return base_prompt
        return base_prompt + "\n\n" + "\n\n".join(blocks)

    def list_packs(self) -> list[str]:
        return list(self._packs.keys())

    def summary(self) -> dict:
        return {
            name: pack.get("title", name)
            for name, pack in self._packs.items()
        }
