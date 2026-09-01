"""Async MCP client. No place_option_order helper."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config.settings import get_settings
from mcp_integration.server_manager import command, mcp_env


def _params() -> StdioServerParameters:
    s = get_settings()
    key, secret = s.execution_credentials()
    if not key:
        raise RuntimeError("ALPACA_API_KEY missing")
    if not secret:
        raise RuntimeError("ALPACA_SECRET_KEY missing")
    cmd = command()
    return StdioServerParameters(
        command=cmd[0],
        args=cmd[1:],
        env=mcp_env(key, secret),
    )


class McpClient:
    def __init__(self, timeout_s: float = 30.0) -> None:
        self.timeout_s = timeout_s

    async def list_tools(self) -> list[dict[str, Any]]:
        params = _params()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=self.timeout_s)
                result = await asyncio.wait_for(session.list_tools(), timeout=self.timeout_s)
                return [
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "inputSchema": getattr(t, "inputSchema", None) or getattr(t, "input_schema", {}),
                    }
                    for t in result.tools
                ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        blocked = (
            name.startswith("place_")
            or name.startswith("cancel_")
            or name.startswith("close_")
            or name.startswith("replace_")
            or name in {"exercise_options_position", "do_not_exercise_options_position"}
        )
        if blocked:
            raise RuntimeError("order tools are not callable from mcp_integration.client")
        params = _params()
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=self.timeout_s)
                return await asyncio.wait_for(
                    session.call_tool(name, arguments or {}),
                    timeout=self.timeout_s,
                )


def list_tools_sync() -> list[dict[str, Any]]:
    return asyncio.run(McpClient().list_tools())
