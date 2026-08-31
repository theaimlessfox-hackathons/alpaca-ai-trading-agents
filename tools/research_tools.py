"""Read-only market wrappers.

This module is the allowlist: only the tool names called out below are ever
reachable through it, regardless of what alpaca-mcp-server adds in the future.
A denylist (block place_/cancel_/close_ by prefix) stops protecting you the
moment the server ships a new mutating tool that doesn't match the prefixes;
an allowlist fails safe by default instead.
"""

from __future__ import annotations

import json
from typing import Any

ALLOWED_TOOLS = frozenset(
    {
        "get_option_chain",
        "get_option_snapshot",
        "get_stock_bars",
        "get_stock_snapshot",
        "get_news",
        "get_clock",
    }
)


def _guard(name: str) -> None:
    if name not in ALLOWED_TOOLS:
        raise RuntimeError(f"research_tools cannot call {name}: not on the read-only allowlist")


def unwrap(result: Any) -> Any:
    """MCP CallToolResult -> parsed JSON payload.

    Also strips alpaca-mcp-server's {"_alpaca_mcp_security": ..., "data": ...}
    security envelope (confirmed live -- every tool response is wrapped this way,
    not documented in the dumped input schemas since those only cover requests).
    """
    content = getattr(result, "content", None)
    parsed: Any = result
    if content:
        parts = [text for block in content if (text := getattr(block, "text", None)) is not None]
        if parts:
            raw = "".join(parts)
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                parsed = raw
    if isinstance(parsed, dict) and "_alpaca_mcp_security" in parsed and "data" in parsed:
        return parsed["data"]
    return parsed


async def _call(name: str, arguments: dict[str, Any]) -> Any:
    _guard(name)
    from mcp_integration.client import McpClient

    return unwrap(await McpClient().call_tool(name, arguments))


async def get_option_chain(
    symbol: str,
    *,
    expiration_date_gte: str | None = None,
    expiration_date_lte: str | None = None,
    strike_price_gte: float | None = None,
    strike_price_lte: float | None = None,
    limit: int = 200,
) -> Any:
    # Confirmed live: an unfiltered call returns an arbitrary ~100-contract page
    # (lexicographic-looking, i.e. lowest strikes first) that isn't centered near
    # spot at all -- for a $769 underlying it came back all deep-ITM calls in the
    # $425-$653 range. Real strike/expiration filters are required to get anything
    # near-the-money, not optional narrowing.
    args: dict[str, Any] = {"underlying_symbol": symbol, "limit": limit}
    if expiration_date_gte:
        args["expiration_date_gte"] = expiration_date_gte
    if expiration_date_lte:
        args["expiration_date_lte"] = expiration_date_lte
    if strike_price_gte is not None:
        args["strike_price_gte"] = strike_price_gte
    if strike_price_lte is not None:
        args["strike_price_lte"] = strike_price_lte
    return await _call("get_option_chain", args)


async def get_option_snapshot(symbols: list[str]) -> Any:
    return await _call("get_option_snapshot", {"symbols": ",".join(symbols)})


async def get_stock_bars(symbol: str, days: int = 20) -> Any:
    # live schema takes "symbols" (comma-separated) and "days" as an int lookback,
    # not "symbol" -- confirmed via a live list_tools()/call_tool() round trip.
    return await _call("get_stock_bars", {"symbols": symbol, "days": days})


async def get_stock_snapshot(symbol: str) -> Any:
    return await _call("get_stock_snapshot", {"symbol": symbol})


async def get_news(symbol: str, limit: int = 5) -> Any:
    return await _call("get_news", {"symbols": symbol, "limit": limit})


async def get_clock() -> Any:
    return await _call("get_clock", {})
