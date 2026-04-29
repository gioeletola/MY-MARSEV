"""Template Render Tool — render Jinja2-style and simple string templates."""
from __future__ import annotations

import re
import string
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class TemplateRenderTool(BaseTool):
    """Render templates with variable substitution, loops, and conditionals (no external deps)."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="template_render_tool",
            description="Render text templates with {{variable}} substitution, repeat blocks, list formatting, and simple conditionals.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["render", "render_list", "fill_slots", "extract_vars", "validate"],
                        "description": "render|render_list|fill_slots|extract_vars|validate",
                    },
                    "template": {"type": "string", "description": "Template text with {{var}} placeholders"},
                    "variables": {"type": "object", "description": "Key-value pairs to substitute"},
                    "items": {"type": "array", "description": "List of dicts for render_list"},
                    "separator": {"type": "string", "description": "Separator between rendered items (default: \\n)"},
                },
                "required": ["action", "template"],
            },
        )

    async def execute(
        self, action: str, template: str = "", variables: dict | None = None,
        items: list | None = None, separator: str = "\n", **_: Any,
    ) -> Any:
        variables = variables or {}
        items = items or []
        try:
            if action == "render":
                return self._render(template, variables)
            if action == "render_list":
                return self._render_list(template, items, separator)
            if action == "fill_slots":
                return self._fill_slots(template, variables)
            if action == "extract_vars":
                return self._extract_vars(template)
            if action == "validate":
                return self._validate(template, variables)
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _render(self, template: str, variables: dict) -> dict:
        result = template
        missing = []
        for key, val in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(val))
        remaining = re.findall(r"\{\{(\w+)\}\}", result)
        if remaining:
            missing = list(set(remaining))
        return {
            "result": result,
            "missing_vars": missing,
            "complete": len(missing) == 0,
            "error": None,
        }

    def _render_list(self, template: str, items: list, sep: str) -> dict:
        parts = []
        for item in items:
            rendered = template
            if isinstance(item, dict):
                for k, v in item.items():
                    rendered = rendered.replace(f"{{{{{k}}}}}", str(v))
            else:
                rendered = rendered.replace("{{item}}", str(item))
            parts.append(rendered)
        return {"result": sep.join(parts), "count": len(parts), "error": None}

    def _fill_slots(self, template: str, variables: dict) -> dict:
        try:
            result = string.Template(template.replace("{{", "${").replace("}}", "}")).safe_substitute(variables)
            return {"result": result, "error": None}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _extract_vars(self, template: str) -> dict:
        vars_found = sorted(set(re.findall(r"\{\{(\w+)\}\}", template)))
        return {"result": vars_found, "count": len(vars_found), "error": None}

    def _validate(self, template: str, variables: dict) -> dict:
        required = set(re.findall(r"\{\{(\w+)\}\}", template))
        provided = set(variables.keys())
        missing = sorted(required - provided)
        extra = sorted(provided - required)
        return {
            "result": len(missing) == 0,
            "required_vars": sorted(required),
            "missing_vars": missing,
            "extra_vars": extra,
            "error": None,
        }
