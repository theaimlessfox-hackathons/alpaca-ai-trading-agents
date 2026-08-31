import pytest


@pytest.fixture(autouse=True)
def _no_live_option_quotes(monkeypatch):
    """Unit tests must not call Alpaca for close-pricing quotes."""
    monkeypatch.setattr("execution.marks.fetch_quotes", lambda _payload: {})
