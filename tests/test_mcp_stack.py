import json
from pathlib import Path

import pytest

from mcp_integration.client import McpClient
from mcp_integration.server_manager import command
from tools.schema_introspect import main as introspect_main


def test_no_place_helper_on_client():
    assert not hasattr(McpClient, "place_option_order")
    src = Path("mcp_integration/client.py").read_text()
    assert "async def place_" not in src


def test_call_tool_blocks_place():
    import asyncio

    with pytest.raises(RuntimeError, match="order tools"):
        asyncio.run(McpClient().call_tool("place_option_order", {"qty": "1"}))


def test_call_tool_blocks_cancel_and_close():
    import asyncio

    for name in ("cancel_order_by_id", "cancel_all_orders", "close_position", "close_all_positions"):
        with pytest.raises(RuntimeError, match="order tools"):
            asyncio.run(McpClient().call_tool(name, {}))


def test_command_uses_uvx_or_binary():
    cmd = command()
    assert cmd
    assert "alpaca-mcp-server" in " ".join(cmd)


def test_introspect_missing_key(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "")
    from config.settings import get_settings

    get_settings.cache_clear()
    assert introspect_main() == 2


def test_live_schema_has_mleg_legs():
    data = json.loads(Path("docs/mcp-schemas/place_option_order.json").read_text())
    props = data["inputSchema"]["properties"]
    assert data["name"] == "place_option_order"
    assert "qty" in data["inputSchema"]["required"]
    assert "legs" in props
    assert "client_order_id" in props
    desc = props["legs"].get("description", "")
    assert "symbol" in desc and "ratio_qty" in desc
