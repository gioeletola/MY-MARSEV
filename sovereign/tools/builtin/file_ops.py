"""Built-in file operations tool."""
from __future__ import annotations

import pathlib
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class FileOpsTool(BaseTool):
    """
    Reads and writes files within the configured data directory.

    Sandboxed to data_dir to prevent path traversal.
    """

    def __init__(self, data_dir: str = "data") -> None:
        self._root = pathlib.Path(data_dir).resolve()

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="file_ops",
            description=(
                "Read or write a file within the data directory. "
                "Use action='read' to retrieve content, 'write' to save content."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "write", "list", "delete"],
                        "description": "The file operation to perform.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Relative path within the data directory.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (required for action='write').",
                    },
                },
                "required": ["action", "path"],
            },
        )

    async def execute(
        self,
        action: str,
        path: str,
        content: str = "",
        **_: Any,
    ) -> Any:
        """Execute a file operation within data_dir."""
        target = self._safe_path(path)

        if action == "read":
            if not target.exists():
                return {"error": f"File not found: {path}"}
            return {"content": target.read_text(encoding="utf-8")}

        if action == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return {"written": str(path), "bytes": len(content)}

        if action == "list":
            if not target.is_dir():
                return {"error": f"Not a directory: {path}"}
            return {"entries": [e.name for e in sorted(target.iterdir())]}

        if action == "delete":
            if target.exists():
                target.unlink()
            return {"deleted": str(path)}

        return {"error": f"Unknown action: {action}"}

    def _safe_path(self, relative: str) -> pathlib.Path:
        """Resolve path and enforce sandbox within data_dir."""
        resolved = (self._root / relative).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise PermissionError(
                f"Path traversal blocked: '{relative}' resolves outside data_dir."
            )
        return resolved
