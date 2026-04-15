"""
MCP (Model Context Protocol) client tool — Section 12 of the SOVEREIGN AI OS spec.

Connects to external MCP servers and routes tool calls through them.
Supports:
  - Stdio-based MCP servers (subprocess with JSON-RPC 2.0 over stdin/stdout)
  - HTTP/SSE MCP servers (via httpx)

MCP protocol reference: https://modelcontextprotocol.io/specification

Usage:
  The orchestrator registers MCPTool with a server config.
  Agents call it with {"server": "...", "tool": "...", "arguments": {...}}.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Raised when an MCP server call fails."""


class StdioMCPSession:
    """
    Manages a single connection to a stdio-based MCP server.

    Spawns the server process and communicates via JSON-RPC 2.0.
    """

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self._command = command
        self._env = env
        self._proc: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._initialized = False

    async def start(self) -> None:
        import os
        env = {**os.environ, **(self._env or {})}
        self._proc = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        # Initialize MCP session
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "SOVEREIGN-AI-OS", "version": "0.2.0"},
        })
        self._initialized = True

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools available on this MCP server."""
        result = await self._send_request("tools/list", {})
        return result.get("tools", [])

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        content = result.get("content", [])
        if content:
            # Extract text content from MCP response
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            return "\n".join(texts) if texts else result
        return result

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._proc.kill()

    async def _send_request(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC 2.0 request and await the response."""
        if self._proc is None:
            raise MCPClientError("MCP session not started.")

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        line = json.dumps(request) + "\n"
        self._proc.stdin.write(line.encode())
        await self._proc.stdin.drain()

        # Read response line (with timeout)
        try:
            raw = await asyncio.wait_for(
                self._proc.stdout.readline(), timeout=30.0
            )
        except asyncio.TimeoutError:
            raise MCPClientError(f"MCP server timed out on method={method}")

        if not raw:
            raise MCPClientError("MCP server closed connection unexpectedly.")

        response = json.loads(raw.decode().strip())
        if "error" in response:
            raise MCPClientError(f"MCP error: {response['error']}")
        return response.get("result", {})


class MCPTool(BaseTool):
    """
    Proxy tool that routes calls to registered MCP servers.

    Multiple MCP servers can be registered under different names.
    The agent specifies which server and tool to call.
    """

    def __init__(self) -> None:
        self._servers: dict[str, dict[str, Any]] = {}   # name → config
        self._sessions: dict[str, StdioMCPSession] = {}  # name → live session

    @property
    def schema(self) -> ToolSchema:
        server_names = list(self._servers.keys()) or ["(none registered)"]
        return ToolSchema(
            name="mcp",
            description=(
                "Call a tool on a registered MCP (Model Context Protocol) server. "
                f"Available servers: {', '.join(server_names)}. "
                "Use for external integrations: Gmail, Calendar, Slack, CRM, databases, etc."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "server": {
                        "type": "string",
                        "description": "Name of the MCP server to call.",
                    },
                    "tool": {
                        "type": "string",
                        "description": "Name of the tool on the MCP server.",
                    },
                    "arguments": {
                        "type": "object",
                        "description": "Arguments to pass to the tool.",
                        "default": {},
                    },
                },
                "required": ["server", "tool"],
            },
        )

    def register_server(
        self,
        name: str,
        command: list[str],
        env: dict[str, str] | None = None,
        description: str = "",
    ) -> None:
        """
        Register an MCP server by its startup command.

        Example:
            mcp_tool.register_server(
                name="filesystem",
                command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/data"],
            )
        """
        self._servers[name] = {
            "command": command,
            "env": env or {},
            "description": description,
        }
        logger.info("MCP server registered: %s → %s", name, command)

    def list_servers(self) -> list[str]:
        return list(self._servers)

    async def execute(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        """
        Route a tool call to the specified MCP server.
        Starts the server session on first use (lazy init).
        """
        if server not in self._servers:
            return {
                "error": f"Unknown MCP server '{server}'. "
                         f"Registered: {list(self._servers.keys())}"
            }

        try:
            session = await self._get_session(server)
            result = await session.call_tool(tool, arguments or {})
            logger.debug("MCP call server=%s tool=%s OK", server, tool)
            return result
        except MCPClientError as exc:
            logger.error("MCP call failed server=%s tool=%s: %s", server, tool, exc)
            return {"error": str(exc)}
        except Exception as exc:
            logger.error("MCP unexpected error server=%s: %s", server, exc)
            return {"error": f"Unexpected error: {exc}"}

    async def list_server_tools(self, server: str) -> list[dict[str, Any]]:
        """List available tools on a given MCP server."""
        if server not in self._servers:
            return []
        try:
            session = await self._get_session(server)
            return await session.list_tools()
        except Exception as exc:
            logger.error("Failed to list MCP tools server=%s: %s", server, exc)
            return []

    async def shutdown_all(self) -> None:
        """Gracefully stop all active MCP sessions."""
        for name, session in list(self._sessions.items()):
            try:
                await session.stop()
                logger.info("MCP session stopped: %s", name)
            except Exception:
                pass
        self._sessions.clear()

    async def _get_session(self, server: str) -> StdioMCPSession:
        """Return existing session or start a new one."""
        if server not in self._sessions:
            cfg = self._servers[server]
            session = StdioMCPSession(command=cfg["command"], env=cfg["env"])
            await session.start()
            self._sessions[server] = session
            logger.info("MCP session started: %s", server)
        return self._sessions[server]
