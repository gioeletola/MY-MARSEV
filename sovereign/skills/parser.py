"""
TOML skill pack parser — reads .toml files and returns SkillDefinition objects.
"""
from __future__ import annotations

import logging
import pathlib
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

from sovereign.skills.types import (
    SkillDefinition, SkillDependency, SkillInput, SkillOutput,
    SkillPermission, SkillStatus,
)

logger = logging.getLogger(__name__)


def _parse_toml(path: pathlib.Path) -> dict[str, Any]:
    if tomllib is None:
        # Pure fallback: very basic key=value parser for CI environments
        data: dict[str, Any] = {}
        section: dict[str, Any] = data
        current_key: str = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_key = line[1:-1]
                keys = current_key.split(".")
                section = data
                for k in keys:
                    section = section.setdefault(k, {})
            elif "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                section[k] = v
        return data
    with path.open("rb") as f:
        return tomllib.load(f)


def parse_skill_file(path: pathlib.Path) -> SkillDefinition | None:
    """Parse a single .toml skill file into a SkillDefinition."""
    try:
        raw = _parse_toml(path)
    except Exception as exc:
        logger.warning("SkillParser: failed to parse %s: %s", path, exc)
        return None

    meta = raw.get("skill", raw)
    try:
        inputs = [
            SkillInput(
                name=i.get("name", ""),
                type=i.get("type", "string"),
                description=i.get("description", ""),
                required=i.get("required", True),
                default=i.get("default"),
            )
            for i in raw.get("inputs", [])
        ]
        outputs = [
            SkillOutput(
                name=o.get("name", ""),
                type=o.get("type", "string"),
                description=o.get("description", ""),
            )
            for o in raw.get("outputs", [])
        ]
        deps = [
            SkillDependency(
                skill_id=d.get("skill_id", d) if isinstance(d, dict) else d,
                optional=d.get("optional", False) if isinstance(d, dict) else False,
            )
            for d in raw.get("dependencies", [])
        ]
        perms = [
            SkillPermission(p) for p in meta.get("permissions", [])
            if p in SkillPermission._value2member_map_
        ]
        status_val = meta.get("status", "active")
        try:
            status = SkillStatus(status_val)
        except ValueError:
            status = SkillStatus.STUB

        skill_id = meta.get("id", path.stem)
        return SkillDefinition(
            skill_id=skill_id,
            name=meta.get("name", skill_id),
            description=meta.get("description", ""),
            version=str(meta.get("version", "1.0.0")),
            status=status,
            permissions=perms,
            tools=meta.get("tools", []),
            agents=meta.get("agents", []),
            inputs=inputs,
            outputs=outputs,
            dependencies=deps,
            prompt_template=raw.get("prompt", {}).get("template", ""),
            tags=meta.get("tags", []),
            author=meta.get("author", "system"),
            requires_approval=meta.get("requires_approval", False),
            source_file=str(path),
            enabled=meta.get("enabled", True),
        )
    except Exception as exc:
        logger.warning("SkillParser: error building SkillDefinition from %s: %s", path, exc)
        return None
