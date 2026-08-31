import asyncio

import pytest

from config.settings import Settings
from execution.account_guard import AccountGuardError, assert_can_submit, resolve_account_id


def test_competition_requires_flag():
    s = Settings(alpaca_account_role="competition", compete_enabled=False, alpaca_paper_trade=True)
    with pytest.raises(AccountGuardError):
        assert_can_submit(account_id="x", settings=s)


def test_account_mismatch():
    s = Settings(expected_account_id="AAA", alpaca_paper_trade=True, alpaca_account_role="sandbox")
    with pytest.raises(AccountGuardError):
        assert_can_submit(account_id="BBB", settings=s)


def test_matching_account_id_passes():
    s = Settings(expected_account_id="AAA", alpaca_paper_trade=True, alpaca_account_role="sandbox")
    assert_can_submit(account_id="AAA", settings=s)  # must not raise


def test_unresolved_account_id_fails_closed_when_expected_is_set():
    """Regression: account_id=None used to silently skip the mismatch check
    entirely. If EXPECTED_ACCOUNT_ID is configured, an unresolved id must raise,
    not pass through."""
    s = Settings(expected_account_id="AAA", alpaca_paper_trade=True, alpaca_account_role="sandbox")
    with pytest.raises(AccountGuardError, match="could not resolve"):
        assert_can_submit(account_id=None, settings=s)


def test_blank_expected_account_id_fails_closed():
    """Live submission requires a nonempty EXPECTED_ACCOUNT_ID. A blank setting
    plus an unresolved account used to pass and defeat the account invariant."""
    s = Settings(expected_account_id="", alpaca_paper_trade=True, alpaca_account_role="sandbox")
    with pytest.raises(AccountGuardError, match="EXPECTED_ACCOUNT_ID"):
        assert_can_submit(account_id=None, settings=s)
    with pytest.raises(AccountGuardError, match="EXPECTED_ACCOUNT_ID"):
        assert_can_submit(account_id="PA123", settings=s)


def test_resolve_account_id_prefers_account_number(monkeypatch):
    async def fake_get_account_info():
        return {"account_number": "PA123", "id": "uuid-1"}

    monkeypatch.setattr("tools.account_tools.get_account_info", fake_get_account_info)
    assert asyncio.run(resolve_account_id()) == "PA123"


def test_resolve_account_id_falls_back_to_id(monkeypatch):
    async def fake_get_account_info():
        return {"id": "uuid-1"}

    monkeypatch.setattr("tools.account_tools.get_account_info", fake_get_account_info)
    assert asyncio.run(resolve_account_id()) == "uuid-1"


def test_resolve_account_id_none_on_failure(monkeypatch):
    async def fake_get_account_info():
        raise RuntimeError("mcp down")

    monkeypatch.setattr("tools.account_tools.get_account_info", fake_get_account_info)
    assert asyncio.run(resolve_account_id()) is None


def test_compete_after_blocks_before_window():
    s = Settings(
        expected_account_id="AAA",
        alpaca_paper_trade=True,
        alpaca_account_role="sandbox",
        compete_after="2099-01-01T00:00:00+00:00",
    )
    with pytest.raises(AccountGuardError, match="compete_after"):
        assert_can_submit(account_id="AAA", settings=s)


def test_compete_after_allows_once_reached():
    s = Settings(
        expected_account_id="AAA",
        alpaca_paper_trade=True,
        alpaca_account_role="sandbox",
        compete_after="2020-01-01",
    )
    assert_can_submit(account_id="AAA", settings=s)


def test_unparseable_compete_after_fails_closed():
    s = Settings(
        expected_account_id="AAA",
        alpaca_paper_trade=True,
        alpaca_account_role="sandbox",
        compete_after="not-a-date",
    )
    with pytest.raises(AccountGuardError, match="compete_after"):
        assert_can_submit(account_id="AAA", settings=s)


def test_resolve_account_id_handles_unwrapped_envelope_shape(monkeypatch):
    """get_account_info may still return the {"data": {...}} envelope shape if
    called before unwrap() strips it -- resolve_account_id should not crash."""

    async def fake_get_account_info():
        return {"_alpaca_mcp_security": {}, "data": {"account_number": "PA999"}}

    monkeypatch.setattr("tools.account_tools.get_account_info", fake_get_account_info)
    assert asyncio.run(resolve_account_id()) == "PA999"
