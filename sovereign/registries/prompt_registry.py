"""
Prompt registry — loads and caches prompt templates from the prompts/ directory.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import pathlib
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_DEFAULT_VERSIONS_PATH = pathlib.Path("data/memory/prompt_versions.json")


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


# ---------------------------------------------------------------------------
# VersionedPromptRegistry
# ---------------------------------------------------------------------------

class VersionedPromptRegistry(PromptRegistry):
    """
    Extends PromptRegistry with version history for every prompt template.

    Version history is persisted to data/memory/prompt_versions.json as:
        {name: [{version, content, timestamp, hash}, ...]}

    Rules:
    - Max 20 versions per prompt (oldest are dropped when exceeded).
    - On first get() the current on-disk content is auto-saved if its hash
      differs from the last recorded version.
    """

    MAX_VERSIONS = 20

    def __init__(
        self,
        prompts_dir: str | pathlib.Path = "prompts",
        versions_path: str | pathlib.Path = _DEFAULT_VERSIONS_PATH,
    ) -> None:
        super().__init__(prompts_dir)
        self._versions_path = pathlib.Path(versions_path)
        # {name: [{version, content, timestamp, hash}]}
        self._history: dict[str, list[dict]] = {}
        self._load_versions()

    # ------------------------------------------------------------------
    # Overridden get() — auto-snapshot on hash change
    # ------------------------------------------------------------------

    def get(self, name: str) -> str:
        content = super().get(name)
        self._auto_snapshot(name, content)
        return content

    # ------------------------------------------------------------------
    # Versioning API
    # ------------------------------------------------------------------

    def save_version(self, name: str, content: str) -> dict:
        """
        Explicitly save *content* as a new version of *name*.
        Returns the version record that was saved.
        """
        versions = self._history.setdefault(name, [])
        new_hash = self._hash(content)

        # Don't duplicate if content identical to latest
        if versions and versions[-1]["hash"] == new_hash:
            return versions[-1]

        record = {
            "version": len(versions) + 1,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hash": new_hash,
        }
        versions.append(record)
        # Trim to MAX_VERSIONS (keep newest)
        if len(versions) > self.MAX_VERSIONS:
            self._history[name] = versions[-self.MAX_VERSIONS:]
        self._persist_versions()
        logger.debug("VersionedPromptRegistry: saved version %d for '%s'", record["version"], name)
        return record

    def get_version(self, name: str, idx: int = -1) -> str:
        """Return the content of a specific version (default: latest)."""
        versions = self._history.get(name, [])
        if not versions:
            return self.get(name)
        return versions[idx]["content"]

    def list_versions(self, name: str) -> list[dict]:
        """Return list of {version, timestamp, hash} for all saved versions."""
        return [
            {
                "version": v["version"],
                "timestamp": v["timestamp"],
                "hash": v["hash"],
            }
            for v in self._history.get(name, [])
        ]

    def diff(self, name: str, v1_idx: int = -2, v2_idx: int = -1) -> str:
        """
        Return a unified diff string between two versions.
        v1_idx / v2_idx are list indices into the version history.
        """
        versions = self._history.get(name, [])
        if len(versions) < 2:
            return "(not enough versions to diff)"
        try:
            v1 = versions[v1_idx]
            v2 = versions[v2_idx]
        except IndexError:
            return "(invalid version indices)"
        lines_a = v1["content"].splitlines(keepends=True)
        lines_b = v2["content"].splitlines(keepends=True)
        diff = difflib.unified_diff(
            lines_a, lines_b,
            fromfile=f"{name} v{v1['version']} ({v1['timestamp'][:10]})",
            tofile=f"{name} v{v2['version']} ({v2['timestamp'][:10]})",
        )
        return "".join(diff) or "(no differences)"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_versions(self) -> None:
        if not self._versions_path.exists():
            return
        try:
            self._history = json.loads(self._versions_path.read_text("utf-8"))
            logger.debug(
                "VersionedPromptRegistry: loaded history for %d prompts",
                len(self._history),
            )
        except Exception as exc:
            logger.warning("VersionedPromptRegistry: load error: %s", exc)

    def _persist_versions(self) -> None:
        try:
            self._versions_path.parent.mkdir(parents=True, exist_ok=True)
            self._versions_path.write_text(
                json.dumps(self._history, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error("VersionedPromptRegistry: persist error: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _auto_snapshot(self, name: str, content: str) -> None:
        """Save a version only if the hash has changed from the last recorded one."""
        versions = self._history.get(name, [])
        new_hash = self._hash(content)
        if not versions or versions[-1]["hash"] != new_hash:
            self.save_version(name, content)
