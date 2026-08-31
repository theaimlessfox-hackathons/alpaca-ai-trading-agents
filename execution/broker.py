"""Only module allowed to call place_option_order. Paper only."""

from __future__ import annotations

import asyncio
from typing import Any

from execution.account_guard import assert_can_submit, resolve_account_id
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config.settings import get_settings
from mcp_integration.server_manager import command


def _broker_params() -> StdioServerParameters:
    s = get_settings()
    if not s.alpaca_paper_trade:
        raise RuntimeError("paper only")
    key, secret = s.execution_credentials()
    cmd = command()
    return StdioServerParameters(
        command=cmd[0],
        args=cmd[1:],
        env={
            "ALPACA_API_KEY": key,
            "ALPACA_SECRET_KEY": secret,
            "ALPACA_PAPER_TRADE": "true",
        },
    )


async def _call_broker(name: str, payload: dict[str, Any]) -> Any:
    params = _broker_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            raw = await session.call_tool(name, payload)
            from tools.research_tools import unwrap

            return unwrap(raw)


async def place_option_order(payload: dict[str, Any]) -> Any:
    # Must be the REAL resolved account, not s.expected_account_id echoed back at
    # itself -- that was a bug (a tautological comparison that could never fail).
    resolved = await resolve_account_id()
    assert_can_submit(account_id=resolved)
    return await _call_broker("place_option_order", payload)


def place_option_order_sync(payload: dict[str, Any]) -> Any:
    return asyncio.run(place_option_order(payload))


async def cancel_order(order_id: str) -> Any:
    return await _call_broker("cancel_order_by_id", {"order_id": order_id})


def cancel_order_sync(order_id: str) -> Any:
    return asyncio.run(cancel_order(order_id))
