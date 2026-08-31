"""Read-only account wrappers. No place/cancel/close."""

from __future__ import annotations

from typing import Any


async def get_account_info() -> Any:
    from mcp_integration.client import McpClient
    from tools.research_tools import unwrap

    return unwrap(await McpClient().call_tool("get_account_info", {}))


async def get_all_positions() -> Any:
    from mcp_integration.client import McpClient
    from tools.research_tools import unwrap

    return unwrap(await McpClient().call_tool("get_all_positions", {}))


async def get_order_by_client_id(client_order_id: str) -> Any:
    from mcp_integration.client import McpClient
    from tools.research_tools import unwrap

    return unwrap(await McpClient().call_tool("get_order_by_client_id", {"client_order_id": client_order_id}))


def get_order_by_client_id_sync(client_order_id: str) -> Any:
    import asyncio

    return asyncio.run(get_order_by_client_id(client_order_id))
