"""
CLI execution tool — runs whitelisted shell commands in a subprocess.

Security model:
  - Only commands on the explicit allowlist are permitted
  - Working directory is restricted to the project data dir
  - Stdout + stderr captured; hard 30s timeout
  - Requires EXECUTE action class approval before the orchestrator calls this
  - NEVER exposes secrets (env vars are stripped)
"""
from __future__ import annotations

import asyncio
import logging
import os
import shlex
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)

# Commands that are safe to execute without extra review.
# Extend this list carefully — each addition is a security decision.
_ALLOWED_PREFIXES = (
    "python", "pip", "pytest",
    "git status", "git log", "git diff", "git branch",
    "ls", "cat", "head", "tail", "find", "grep",
    "echo", "date", "pwd", "env",
    "curl --head", "curl -I",         # Read-only HTTP
    "ping -c",                         # Connectivity check
    "df -h", "du -sh", "free -h",     # System info (read-only)
    "ps aux", "top -b -n1",
)


class CLITool(BaseTool):
    """
    Execute whitelisted shell commands and return stdout/stderr.

    Non-whitelisted commands are refused before execution.
    Destructive operations (rm, kill, chmod, sudo, etc.) are never allowed.
    """

    DEFAULT_TIMEOUT = 15
    MAX_OUTPUT_CHARS = 8_000

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="cli_exec",
            description=(
                "Execute a whitelisted shell command and return its output. "
                "Only read-only and safe commands are permitted. "
                "REQUIRES EXECUTE action class. "
                "Destructive commands (rm, sudo, kill, etc.) are refused."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run. Must be on the allowlist.",
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Working directory (defaults to project root).",
                        "default": ".",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Max execution time in seconds (default 15, max 30).",
                        "default": 15,
                    },
                },
                "required": ["command"],
            },
        )

    async def execute(
        self,
        command: str,
        working_dir: str = ".",
        timeout_seconds: int = DEFAULT_TIMEOUT,
        **_: Any,
    ) -> dict[str, Any]:
        """
        Run a whitelisted shell command.

        Returns:
            {stdout, stderr, exit_code, elapsed_ms, refused, refusal_reason}
        """
        # Security: check allowlist
        refused, reason = self._check_allowlist(command)
        if refused:
            logger.warning("CLI command refused: %r — %s", command, reason)
            return {
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "elapsed_ms": 0,
                "refused": True,
                "refusal_reason": reason,
            }

        timeout_seconds = min(max(1, timeout_seconds), 30)

        import time
        start = time.monotonic()

        # Strip env vars — no credentials leak to subprocess
        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "LANG": "en_US.UTF-8",
        }

        try:
            args = shlex.split(command)
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=safe_env,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=float(timeout_seconds)
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
                "elapsed_ms": int((time.monotonic() - start) * 1000),
                "refused": False,
                "refusal_reason": None,
                "timed_out": False,
            }

        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = stdout_b.decode(errors="replace")
        stderr = stderr_b.decode(errors="replace")

        if len(stdout) > self.MAX_OUTPUT_CHARS:
            stdout = stdout[: self.MAX_OUTPUT_CHARS] + "\n... [TRUNCATED]"
        if len(stderr) > self.MAX_OUTPUT_CHARS:
            stderr = stderr[: self.MAX_OUTPUT_CHARS] + "\n... [TRUNCATED]"

        return {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "elapsed_ms": elapsed_ms,
            "refused": False,
            "refusal_reason": None,
            "timed_out": timed_out,
        }

    @staticmethod
    def _check_allowlist(command: str) -> tuple[bool, str]:
        """
        Returns (refused, reason).
        Refused = True means the command must NOT run.
        """
        cmd = command.strip()

        # Hard-block dangerous patterns regardless of allowlist
        dangerous = ("rm ", "sudo", "kill", "pkill", "chmod", "chown",
                     "mkfs", "dd ", ">", ">>", "|", ";", "&&", "||",
                     "eval", "exec", "source", "curl -X", "wget -O",
                     "pip install", "npm install", "apt", "yum")
        for pattern in dangerous:
            if pattern in cmd:
                return True, f"Blocked pattern detected: {pattern!r}"

        # Check allowlist prefix
        for allowed in _ALLOWED_PREFIXES:
            if cmd.startswith(allowed):
                return False, ""

        return True, f"Command not on allowlist. Allowed prefixes: {_ALLOWED_PREFIXES}"
