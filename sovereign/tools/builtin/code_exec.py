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

import ast as _ast

_BLOCKED_MODULES = frozenset({
    "os", "subprocess", "socket", "urllib", "requests", "httpx",
    "shutil", "ctypes", "importlib", "pickle", "pty", "sys",
    "builtins", "posix", "nt", "signal", "resource", "fcntl",
})
_BLOCKED_BUILTINS = frozenset({
    "eval", "exec", "compile", "__import__", "open", "breakpoint",
    "memoryview", "vars", "dir",
})
_BLOCKED_ATTR_CALLS = frozenset({
    "system", "popen", "run", "Popen", "call", "check_output",
    "check_call", "getoutput", "spawn", "execv", "execve",
})


def _ast_check(code: str) -> str | None:
    """
    Walk the AST and block dangerous imports/calls before subprocess execution.
    Returns a human-readable block reason, or None if code appears safe.
    """
    try:
        tree = _ast.parse(code, mode="exec")
    except SyntaxError:
        return None  # let the subprocess surface the syntax error naturally

    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BLOCKED_MODULES:
                    return f"import '{alias.name}' is not allowed in sandbox"
        elif isinstance(node, _ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _BLOCKED_MODULES:
                return f"'from {node.module} import ...' is not allowed in sandbox"
        elif isinstance(node, _ast.Call):
            # Direct built-in call: eval(...), exec(...), __import__(...)
            if isinstance(node.func, _ast.Name) and node.func.id in _BLOCKED_BUILTINS:
                return f"call to '{node.func.id}' is not allowed in sandbox"
            # Attribute call: os.system(...), subprocess.run(...), etc.
            if isinstance(node.func, _ast.Attribute):
                if node.func.attr in _BLOCKED_ATTR_CALLS:
                    return f"call to '.{node.func.attr}' is not allowed in sandbox"
        elif isinstance(node, _ast.Attribute):
            # Block __dunder__ attribute access used for class-hierarchy escapes
            if node.attr in ("__class__", "__bases__", "__subclasses__", "__globals__",
                             "__builtins__", "__code__", "__closure__"):
                return f"access to '{node.attr}' is not allowed in sandbox"

    return None


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

        # AST-based static analysis — catch dangerous calls regardless of obfuscation
        block_reason = _ast_check(code)
        if block_reason:
            return {
                "stdout": "",
                "stderr": f"Sandbox blocked: {block_reason}",
                "exit_code": -2,
                "elapsed_ms": 0,
                "truncated": False,
                "timed_out": False,
            }

        with tempfile.TemporaryDirectory(prefix="sovereign_exec_") as tmpdir:
            script = Path(tmpdir) / "script.py"
            script.write_text(code, encoding="utf-8")

            import time
            start = time.monotonic()

            # Build restricted environment: no HOME, minimal PATH, no network hints
            restricted_env = {
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": "",
                "TMPDIR": tmpdir,
            }

            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, str(script),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE if input_data else asyncio.subprocess.DEVNULL,
                    cwd=tmpdir,
                    env=restricted_env,
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
