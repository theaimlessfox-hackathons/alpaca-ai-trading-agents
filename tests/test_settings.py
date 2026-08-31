import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from config.settings import Settings, get_settings


def _isolated(**overrides) -> Settings:
    drop = {
        k
        for k in os.environ
        if k.upper().startswith("ALPACA_")
        or k.upper()
        in {"COMPETE_ENABLED", "EXPECTED_ACCOUNT_ID", "COMPETE_AFTER", "UNIVERSE"}
    }
    env = {k: v for k, v in os.environ.items() if k not in drop}
    with patch.dict(os.environ, env, clear=True):
        return Settings(_env_file=None, **overrides)


def test_universe():
    assert get_settings().universe == ("SPY", "QQQ", "IWM")
    assert _isolated().universe == ("SPY", "QQQ", "IWM")


def test_iv_rv_knobs():
    s = _isolated()
    assert s.rv_lookback_days == 20
    assert s.iv_rv_rich_min > 0


def test_paper_default_true():
    s = _isolated()
    assert s.alpaca_paper_trade is True
    assert s.paper_trade is True


def test_compete_default_false():
    assert _isolated().compete_enabled is False


def test_live_constructor_rejected():
    with pytest.raises(ValidationError):
        _isolated(alpaca_paper_trade=False)


def test_execution_credentials_sandbox_uses_generic_keys():
    s = _isolated(alpaca_api_key="gen-key", alpaca_secret_key="gen-secret")
    assert s.execution_credentials() == ("gen-key", "gen-secret")


def test_execution_credentials_competition_requires_comp_keys():
    with pytest.raises(RuntimeError, match="competition credentials"):
        _isolated(
            alpaca_account_role="competition",
            compete_enabled=True,
            alpaca_api_key="gen-key",
            alpaca_secret_key="gen-secret",
        ).execution_credentials()


def test_execution_credentials_competition_uses_comp_keys():
    s = _isolated(
        alpaca_account_role="competition",
        compete_enabled=True,
        alpaca_api_key="gen-key",
        alpaca_secret_key="gen-secret",
        alpaca_competition_api_key="comp-key",
        alpaca_competition_secret_key="comp-secret",
    )
    assert s.execution_credentials() == ("comp-key", "comp-secret")


def test_compete_window_open():
    from datetime import datetime, timezone

    from config.settings import parse_compete_after

    assert parse_compete_after("") is None
    assert parse_compete_after("nope") is None
    parsed = parse_compete_after("2026-09-01")
    assert parsed == datetime(2026, 9, 1, tzinfo=timezone.utc)
    s = _isolated(compete_after="2020-01-01")
    assert s.compete_window_open() is True
    s = _isolated(compete_after="2099-01-01T00:00:00+00:00")
    assert s.compete_window_open() is False


def test_live_env_rejected():
    env = {k: v for k, v in os.environ.items() if k.upper() != "ALPACA_PAPER_TRADE"}
    env["ALPACA_PAPER_TRADE"] = "false"
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
