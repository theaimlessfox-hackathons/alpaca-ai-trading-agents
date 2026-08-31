from config.settings import Settings
from strategy.regime import (
    StandDown,
    Trade,
    atm_iv_from_candidates,
    compute_regime_inputs,
    decide,
    detect_breakout,
    iv_rv_ratio,
    realized_vol_20,
    spot_from_bars,
)


def test_ratio():
    assert iv_rv_ratio(0.20, 0.10) == 2.0


def test_rich():
    s = Settings()
    out = decide(atm_iv=0.20, rv_20=0.10, rv_bar_count=20, breakout=False, settings=s)
    assert isinstance(out, Trade)
    assert out.iv_rv == 2.0


def test_cheap():
    s = Settings()
    out = decide(atm_iv=0.10, rv_20=0.12, rv_bar_count=20, breakout=False, settings=s)
    assert isinstance(out, StandDown)
    assert out.reason == "cheap_iv_rv"


def test_breakout():
    out = decide(atm_iv=0.20, rv_20=0.10, rv_bar_count=20, breakout=True, settings=Settings())
    assert isinstance(out, StandDown) and out.reason == "breakout"


def test_missing():
    out = decide(atm_iv=None, rv_20=0.10, rv_bar_count=20, breakout=False, settings=Settings())
    assert isinstance(out, StandDown) and out.reason == "insufficient_data"
    out = decide(atm_iv=0.2, rv_20=0.1, rv_bar_count=10, breakout=False, settings=Settings())
    assert out.reason == "insufficient_data"


def _quiet_bars(n=25, start=500.0, step=0.05):
    bars = []
    price = start
    for i in range(n):
        price += step if i % 2 == 0 else -step
        bars.append({"c": price, "h": price + 0.5, "l": price - 0.5})
    return bars


def test_realized_vol_needs_at_least_two_closes():
    assert realized_vol_20([{"c": 500.0}])[0] is None
    assert realized_vol_20([])[0] is None


def test_realized_vol_positive_for_moving_series():
    rv, count = realized_vol_20(_quiet_bars(25), lookback_days=20)
    assert rv is not None and rv > 0
    assert count == 20


def test_realized_vol_snake_case_keys():
    bars = [{"close": 500.0}, {"close": 502.0}, {"close": 498.0}, {"close": 501.0}]
    rv, count = realized_vol_20(bars, lookback_days=20)
    assert rv is not None
    assert count == 3


def test_detect_breakout_false_on_quiet_series():
    assert detect_breakout(_quiet_bars(10)) is False


def test_detect_breakout_true_on_range_spike():
    bars = _quiet_bars(10)
    last_close = bars[-1]["c"]
    bars.append({"c": last_close + 5, "h": last_close + 10, "l": last_close - 10})
    assert detect_breakout(bars) is True


def test_detect_breakout_needs_minimum_bars():
    assert detect_breakout(_quiet_bars(3)) is False


def test_atm_iv_from_candidates_picks_nearest_strike():
    candidates = [
        {"strike": 490, "iv": 0.30},
        {"strike": 500, "iv": 0.20},
        {"strike": 510, "iv": 0.25},
    ]
    assert atm_iv_from_candidates(candidates, spot=501.0) == 0.20


def test_atm_iv_from_candidates_handles_empty_or_missing_spot():
    assert atm_iv_from_candidates([], spot=500.0) is None
    assert atm_iv_from_candidates([{"strike": 500, "iv": 0.2}], spot=None) is None


def test_spot_from_bars_uses_last_close():
    bars = [{"c": 498.0}, {"c": 500.0}, {"h": 505.0, "l": 495.0}]  # last bar missing close
    assert spot_from_bars(bars) == 500.0


def test_compute_regime_inputs_end_to_end():
    bars = _quiet_bars(25)
    spot = bars[-1]["c"]
    sliced = {
        "short_candidates": [{"strike": round(spot), "iv": 0.30}],
        "long_candidates": [{"strike": round(spot) - 5, "iv": 0.32}],
    }
    out = compute_regime_inputs(sliced, bars)
    assert out["rv_20"] is not None
    assert out["rv_bar_count"] == 20
    assert out["breakout"] is False
    assert out["atm_iv"] in (0.30, 0.32)


def test_atm_iv_uses_all_banded_not_otm_delta_set():
    bars = _quiet_bars(25)
    sliced = {
        "short_candidates": [{"strike": 480, "iv": 0.40}],
        "long_candidates": [{"strike": 470, "iv": 0.42}],
        "all_banded": [
            {"strike": 480, "iv": 0.40},
            {"strike": 500, "iv": 0.20},
            {"strike": 470, "iv": 0.42},
        ],
    }
    out = compute_regime_inputs(sliced, bars)
    assert out["atm_iv"] == 0.20
