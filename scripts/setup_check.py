#!/usr/bin/env python3
"""Env-only check. Live MCP/CLI pings are alpaca-stack/010."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_settings


async def _account_number_with_keys(api_key: str, secret_key: str) -> str | None:
    """Query get_account_info with an explicit key pair, bypassing McpClient's
    global-settings key resolution -- needed to print the competition account's
    id separately from whichever keys are currently active."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    from mcp_integration.server_manager import command
    from tools.research_tools import unwrap

    params = StdioServerParameters(
        command=command()[0],
        args=command()[1:],
        env={"ALPACA_API_KEY": api_key, "ALPACA_SECRET_KEY": secret_key, "ALPACA_PAPER_TRADE": "true"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            raw = await session.call_tool("get_account_info", {})
    info = unwrap(raw)
    data = info.get("data", info) if isinstance(info, dict) else info
    return data.get("account_number") if isinstance(data, dict) else None


def main() -> int:
    try:
        s = get_settings()
    except Exception as exc:
        print("FAIL: settings load rejected", exc)
        return 1
    if not s.alpaca_paper_trade or not s.paper_trade:
        print("FAIL: ALPACA_PAPER_TRADE must be true")
        return 1
    missing = []
    if not s.resolved_api_key():
        missing.append("ALPACA_API_KEY")
    if not s.alpaca_secret_key:
        missing.append("ALPACA_SECRET_KEY")
    if not s.featherless_api_key:
        missing.append("FEATHERLESS_API_KEY")
    if missing:
        print("FAIL: missing", ", ".join(missing))
        return 1
    if s.compete_enabled and not s.expected_account_id:
        print("FAIL: COMPETE_ENABLED requires EXPECTED_ACCOUNT_ID")
        return 1
    print("ok paper=true role=", s.alpaca_account_role, "compete=", s.compete_enabled)
    print("universe", s.universe)
    failed = False
    if s.alpaca_api_key:
        try:
            from mcp_integration.client import list_tools_sync

            tools = list_tools_sync()
            print("mcp_tools", len(tools))
        except Exception as exc:
            print("mcp_ping_fail", type(exc).__name__, exc)
            return 1

        # account equity + options level, and clock -- these were named in this
        # epic's own success criteria but never actually implemented here.
        import asyncio

        try:
            from tools.account_tools import get_account_info

            info = asyncio.run(get_account_info())
            data = info.get("data", info) if isinstance(info, dict) else info
            if isinstance(data, dict):
                print(
                    f"account[{s.alpaca_account_role}]",
                    data.get("account_number"),
                    "equity",
                    data.get("portfolio_value"),
                    "options_level",
                    data.get("options_trading_level"),
                )
        except Exception as exc:
            print("account_ping_fail", type(exc).__name__, exc)
            failed = True

        # Print both IDs, not just whichever key pair is currently active --
        # this was the actual gap in 011 (only ever printed one account). The
        # primary keys above are printed tagged by s.alpaca_account_role
        # (sandbox or competition, whichever is currently configured); if a
        # *separate* competition key pair also exists, query and print that too.
        if s.alpaca_competition_api_key and s.alpaca_competition_secret_key:
            try:
                comp_id = asyncio.run(
                    _account_number_with_keys(s.alpaca_competition_api_key, s.alpaca_competition_secret_key)
                )
                print("account[competition]", comp_id)
            except Exception as exc:
                print("competition_account_ping_fail", type(exc).__name__, exc)
                failed = True
        elif s.competing():
            print("FAIL: competition credentials missing")
            failed = True

        try:
            from tools.research_tools import get_clock

            clock = asyncio.run(get_clock())
            data = clock.get("data", clock) if isinstance(clock, dict) else clock
            if isinstance(data, dict):
                print("clock", "open" if data.get("is_open") else "closed")
            else:
                print("clock_ping_fail", "bad_shape")
                failed = True
        except Exception as exc:
            print("clock_ping_fail", type(exc).__name__, exc)
            failed = True
    else:
        print("mcp_ping skipped (no ALPACA_API_KEY)")
        failed = True

    try:
        from cli_integration.ops import account

        if account():
            print("cli_account", "ok")
        else:
            print("cli_account", "empty")
            failed = True
    except FileNotFoundError:
        print("cli_account_fail", "alpaca CLI not installed")
        failed = True
    except Exception as exc:
        print("cli_account_fail", type(exc).__name__)
        failed = True

    from agents.llm import smoke

    fw = smoke()
    print("featherless", "ok" if fw.ok else f"fail ({fw.error})")
    if not fw.ok:
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
