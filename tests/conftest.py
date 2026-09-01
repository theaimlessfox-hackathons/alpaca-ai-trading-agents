import pytest


@pytest.fixture(autouse=True)
def _no_live_option_quotes(monkeypatch):
    """Unit tests must not call Alpaca for quotes or order reconciliation."""
    monkeypatch.setattr("execution.marks.fetch_quotes", lambda _payload: {})
    monkeypatch.setattr(
        "tools.account_tools.get_order_by_client_id_sync",
        lambda _client_order_id: {"status": "new", "filled_qty": "0"},
    )
    # Pin the watchlist so validate()/iter_universe() never hit market data.
    monkeypatch.setenv("UNIVERSE_MODE", "pinned")
    from config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
