from strategy.signals import filter_symbol, iter_universe


def test_universe_lock():
    assert iter_universe() == ["SPY", "QQQ", "IWM"]
    assert filter_symbol("NVDA") is None
    assert filter_symbol("SPY") == "SPY"
