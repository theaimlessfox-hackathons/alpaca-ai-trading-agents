from config.settings import Settings
from strategy.signals import filter_symbol, iter_universe


def test_pinned_universe():
    s = Settings(universe_mode="pinned", universe=("SPY", "QQQ", "IWM"))
    assert iter_universe(s) == ["SPY", "QQQ", "IWM"]
    assert filter_symbol("NVDA", s) is None
    assert filter_symbol("SPY", s) == "SPY"


def test_discover_universe_uses_alpaca_rank(monkeypatch):
    from strategy import universe as uni

    uni.clear_universe_cache()
    monkeypatch.setattr(uni, "fetch_most_actives", lambda **_k: ["NVDA", "TSLA", "META"])
    monkeypatch.setattr(uni, "fetch_movers", lambda **_k: ["AMD", "NVDA"])
    monkeypatch.setattr(uni, "asset_optionable", lambda sym, **_k: True)
    monkeypatch.setattr(uni, "last_prices", lambda _syms, **_k: {s: 50.0 for s in _syms})
    s = Settings(universe_mode="discover", universe_size=4)
    assert iter_universe(s) == ["NVDA", "TSLA", "META", "AMD"]
    assert filter_symbol("NVDA", s) == "NVDA"
    assert filter_symbol("SPY", s) is None
