import asyncio
from dataclasses import dataclass

import pytest

from tools.research_tools import ALLOWED_TOOLS, _guard, unwrap


def test_allowlist_permits_known_read_tools():
    for name in ("get_option_chain", "get_option_snapshot", "get_stock_bars", "get_stock_snapshot", "get_news", "get_clock"):
        _guard(name)  # must not raise


def test_allowlist_blocks_everything_else():
    for name in ("place_option_order", "cancel_order_by_id", "cancel_all_orders", "close_position", "close_all_positions", "some_future_tool"):
        with pytest.raises(RuntimeError):
            _guard(name)


def test_allowlist_is_exactly_the_read_surface():
    assert ALLOWED_TOOLS == {
        "get_option_chain",
        "get_option_snapshot",
        "get_stock_bars",
        "get_stock_snapshot",
        "get_news",
        "get_clock",
    }


@dataclass
class _Block:
    text: str


@dataclass
class _Result:
    content: list


def test_unwrap_parses_json_text_content():
    result = _Result(content=[_Block(text='{"a": 1}')])
    assert unwrap(result) == {"a": 1}


def test_unwrap_joins_multiple_text_blocks():
    result = _Result(content=[_Block(text="{"), _Block(text='"a": 1}')])
    assert unwrap(result) == {"a": 1}


def test_unwrap_returns_raw_text_when_not_json():
    result = _Result(content=[_Block(text="not json")])
    assert unwrap(result) == "not json"


def test_unwrap_passes_through_when_no_content():
    assert unwrap("already a plain value") == "already a plain value"


def test_call_tool_from_research_tools_rejects_place(monkeypatch):
    from tools import research_tools

    with pytest.raises(RuntimeError, match="allowlist"):
        asyncio.run(research_tools._call("place_option_order", {}))
