"""
Code execution tool — runs Python in a sandboxed subprocess.

Security model:
  - Executes in a child process (process isolation)
  - Hard timeout enforced via asyncio.wait_for
  - stdout + stderr captured and returned
  - No network access to the subprocess (OS-level; not enforced here — add
    seccomp/nsjail for production hardening)
  - Working directory is an isolated temp dir (auto-cleaned)
  - Requires EXECUTE action class approval before the orchestrator calls this
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


class CodeExecTool(BaseTool):
    """
    Executes Python snippets in a sandboxed subprocess.

    Returns stdout, stderr, exit code, and elapsed time.
    Hard timeout defaults to 15 seconds.
    """

    DEFAULT_TIMEOUT = 15
    MAX_OUTPUT_CHARS = 8_000   # Truncate very large outputs

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="code_exec",
            description=(
                "Execute a Python code snippet and return its output. "
                "Use for calculations, data transformations, or scripting. "
                "REQUIRES EXECUTE action class. Has a 15-second hard timeout. "
                "No persistent state between calls."
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
                        "description": "Max execution time in seconds (default 15, max 30).",
                        "default": 15,
                    },
                    "input_data": {
                        "type": "string",
                        "description": "Optional stdin data to pass to the program.",
                        "default": "",
                    },
                },
                "required": ["code"],
            },
        )

    async def execute(
        self,
        code: str,
        timeout_seconds: int = DEFAULT_TIMEOUT,
        input_data: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        """
        Run code in an isolated subprocess with timeout.

        Returns:
            {stdout, stderr, exit_code, elapsed_ms, truncated}
        """
        timeout_seconds = min(max(1, timeout_seconds), 30)

        with tempfile.TemporaryDirectory(prefix="sovereign_exec_") as tmpdir:
            script = Path(tmpdir) / "script.py"
            script.write_text(code, encoding="utf-8")

            import time
            start = time.monotonic()

            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, str(script),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE if input_data else asyncio.subprocess.DEVNULL,
                    cwd=tmpdir,
                )
                stdin_bytes = input_data.encode() if input_data else None

                try:
                    stdout_b, stderr_b = await asyncio.wait_for(
                        proc.communicate(input=stdin_bytes),
                        timeout=timeout_seconds,
                    )
                    exit_code = proc.returncode or 0
                    timed_out = False
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.communicate()
                    stdout_b, stderr_b = b"", b"[TIMEOUT]".encode()
                    exit_code = -1
                    timed_out = True

            except Exception as exc:
                return {
                    "stdout": "",
                    "stderr": str(exc),
                    "exit_code": -1,
                    "elapsed_ms": 0,
                    "truncated": False,
                    "timed_out": False,
                }

            elapsed_ms = int((time.monotonic() - start) * 1000)
            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")

            truncated = False
            if len(stdout) > self.MAX_OUTPUT_CHARS:
                stdout = stdout[: self.MAX_OUTPUT_CHARS] + "\n... [TRUNCATED]"
                truncated = True
            if len(stderr) > self.MAX_OUTPUT_CHARS:
                stderr = stderr[: self.MAX_OUTPUT_CHARS] + "\n... [TRUNCATED]"

            return {
                "stdout":     stdout,
                "stderr":     stderr,
                "exit_code":  exit_code,
                "elapsed_ms": elapsed_ms,
                "truncated":  truncated,
                "timed_out":  timed_out,
            }
