from strategy.blackscholes import bs_delta, bs_price, implied_vol, iv_and_delta_from_price


def test_atm_call_delta_near_half():
    d = bs_delta(500, 500, 14 / 365, 0.20, right="call")
    assert 0.45 < d < 0.60


def test_atm_put_delta_near_negative_half():
    d = bs_delta(500, 500, 14 / 365, 0.20, right="put")
    assert -0.60 < d < -0.45


def test_deep_otm_put_delta_small_magnitude():
    d = bs_delta(500, 400, 14 / 365, 0.20, right="put")
    assert -0.05 < d < 0


def test_deep_itm_call_delta_near_one():
    d = bs_delta(500, 300, 14 / 365, 0.20, right="call")
    assert d > 0.95


def test_price_is_zero_at_zero_vol_below_strike_call():
    assert bs_price(400, 500, 14 / 365, 0.0, right="call") == 0.0


def test_price_is_intrinsic_at_expiry():
    assert bs_price(520, 500, 0, 0.20, right="call") == 20.0
    assert bs_price(480, 500, 0, 0.20, right="put") == 20.0


def test_implied_vol_round_trips_through_price():
    price = bs_price(500, 495, 14 / 365, 0.22, right="put")
    iv = implied_vol(price, 500, 495, 14 / 365, right="put")
    assert iv is not None
    assert abs(iv - 0.22) < 1e-3


def test_implied_vol_none_below_intrinsic():
    assert implied_vol(0.01, 400, 500, 14 / 365, right="put") is None


def test_iv_and_delta_from_price_are_internally_consistent():
    true_iv = 0.18
    price = bs_price(500, 500, 14 / 365, true_iv, right="call")
    iv, delta = iv_and_delta_from_price(price, 500, 500, 14, right="call")
    assert iv is not None and abs(iv - true_iv) < 1e-3
    assert delta is not None
    assert abs(delta - bs_delta(500, 500, 14 / 365, true_iv, right="call")) < 1e-6


def test_iv_and_delta_from_price_none_on_bad_price():
    iv, delta = iv_and_delta_from_price(0.0, 500, 500, 14, right="call")
    assert iv is None and delta is None
