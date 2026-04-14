"""
Built-in code execution tool stub.

WARNING: Executing arbitrary code is a high-risk operation.
This stub requires explicit EXECUTE action class approval before running.
Replace the execute() body with a sandboxed execution environment
(e.g. Docker, Pyodide, E2B, Jupyter kernel) before enabling in production.
"""
from __future__ import annotations

from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class CodeExecTool(BaseTool):
    """
    Executes a snippet of Python code and returns the output.

    Stub implementation — do NOT use the naive exec() approach in production.
    Requires an isolated sandbox (Docker, E2B, etc.).
    """

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="code_exec",
            description=(
                "Execute a Python code snippet and return its stdout output. "
                "Use for calculations, data transformations, or script execution. "
                "REQUIRES EXECUTE action class. Code runs in an isolated sandbox."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Maximum execution time in seconds (default 10).",
                        "default": 10,
                    },
                },
                "required": ["code"],
            },
        )

    async def execute(self, code: str, timeout_seconds: int = 10, **_: Any) -> dict[str, Any]:
        """
        Execute Python code in an isolated sandbox.

        TODO: Replace with a real sandbox (E2B, Docker subprocess, etc.).
        """
        # Stub: do not execute real code — return a placeholder
        return {
            "stdout": "[STUB] Code execution sandbox not yet connected.",
            "stderr": "",
            "exit_code": 0,
            "note": (
                "Wire up a real sandbox (E2B, Docker, Pyodide) "
                "before enabling code execution in production."
            ),
        }
