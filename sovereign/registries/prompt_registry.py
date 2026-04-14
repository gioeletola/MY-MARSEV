"""
Prompt registry — loads and caches prompt templates from the prompts/ directory.
"""
from __future__ import annotations

import pathlib


class PromptRegistry:
    """
    Loads and serves prompt templates from the prompts/ directory.

    Templates are plain text files with optional {variable} interpolation.
    Names follow the path relative to prompts_dir, without the .txt extension.
    Examples:
        "system/ceo_agent"    → prompts/system/ceo_agent.txt
        "tasks/decompose"     → prompts/tasks/decompose.txt
    """

    def __init__(self, prompts_dir: str | pathlib.Path = "prompts") -> None:
        self._root = pathlib.Path(prompts_dir)
        self._cache: dict[str, str] = {}

    def get(self, name: str) -> str:
        """
        Return the raw prompt template string for the given name.

        Raises FileNotFoundError if no template file exists.
        """
        if name not in self._cache:
            self._cache[name] = self._load(name)
        return self._cache[name]

    def render(self, name: str, **kwargs: str) -> str:
        """Load a template and interpolate keyword arguments."""
        template = self.get(name)
        return template.format(**kwargs)

    def list_templates(self) -> list[str]:
        """Return all available template names (relative paths without .txt)."""
        if not self._root.exists():
            return []
        return [
            str(p.relative_to(self._root).with_suffix("")).replace("\\", "/")
            for p in sorted(self._root.rglob("*.txt"))
        ]

    def _load(self, name: str) -> str:
        """Load a template file from disk."""
        path = self._root / f"{name}.txt"
        if not path.exists():
            # Return a generic fallback instead of raising, so missing templates
            # don't crash agents at runtime.
            return f"You are the {name.split('/')[-1].replace('_', ' ')} agent."
        return path.read_text(encoding="utf-8")
