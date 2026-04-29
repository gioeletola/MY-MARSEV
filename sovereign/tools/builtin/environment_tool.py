"""Environment Tool — inspect runtime environment, Python info, OS info."""
from __future__ import annotations

import os
import platform
import sys
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

_SAFE_ENV_PREFIXES = ("PATH", "HOME", "USER", "SHELL", "LANG", "TERM", "PWD", "TMPDIR", "TMP", "TEMP")
_BLOCKED_PATTERNS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "PASS", "PWD", "AUTH", "CRED")


def _is_safe_var(name: str) -> bool:
    upper = name.upper()
    return not any(p in upper for p in _BLOCKED_PATTERNS)


class EnvironmentTool(BaseTool):
    """Inspect the runtime environment: Python version, OS info, env vars, cwd, path."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="environment_tool",
            description="Inspect runtime environment: Python version, OS, platform, env vars (safe only), cwd, sys.path, CPU count.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["python_info", "os_info", "env_var", "env_list",
                                 "cwd", "sys_path", "platform_info", "runtime_summary"],
                        "description": "python_info|os_info|env_var|env_list|cwd|sys_path|platform_info|runtime_summary",
                    },
                    "name": {"type": "string", "description": "Env var name for env_var action"},
                    "prefix": {"type": "string", "description": "Filter prefix for env_list"},
                },
                "required": ["action"],
            },
        )

    async def execute(self, action: str, name: str = "", prefix: str = "", **_: Any) -> Any:
        try:
            if action == "python_info":
                return {
                    "result": {
                        "version": sys.version,
                        "version_info": list(sys.version_info),
                        "executable": sys.executable,
                        "implementation": platform.python_implementation(),
                        "compiler": platform.python_compiler(),
                    },
                    "error": None,
                }
            if action == "os_info":
                return {
                    "result": {
                        "system": platform.system(),
                        "node": platform.node(),
                        "release": platform.release(),
                        "machine": platform.machine(),
                        "processor": platform.processor(),
                    },
                    "error": None,
                }
            if action == "platform_info":
                return {
                    "result": {
                        "platform": platform.platform(),
                        "architecture": platform.architecture(),
                        "cpu_count": os.cpu_count(),
                        "pid": os.getpid(),
                    },
                    "error": None,
                }
            if action == "env_var":
                if not name:
                    return {"result": None, "error": "name is required"}
                if not _is_safe_var(name):
                    return {"result": None, "error": f"Access to '{name}' is blocked for security reasons"}
                val = os.environ.get(name)
                return {"result": val, "found": val is not None, "error": None}
            if action == "env_list":
                filtered = {
                    k: v for k, v in os.environ.items()
                    if _is_safe_var(k) and (not prefix or k.upper().startswith(prefix.upper()))
                }
                return {"result": filtered, "count": len(filtered), "error": None}
            if action == "cwd":
                return {"result": os.getcwd(), "error": None}
            if action == "sys_path":
                return {"result": sys.path, "count": len(sys.path), "error": None}
            if action == "runtime_summary":
                return {
                    "result": {
                        "python": sys.version.split()[0],
                        "system": platform.system(),
                        "machine": platform.machine(),
                        "cpu_count": os.cpu_count(),
                        "cwd": os.getcwd(),
                        "pid": os.getpid(),
                    },
                    "error": None,
                }
            return {"result": None, "error": f"Unknown action: {action}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}
