from risk.engine import Leg, PortfolioView, ProposalView, computed_max_loss, validate
from risk.types import Approve, Veto
from config.settings import Settings


def good_legs():
    return [
        Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.18),
        Leg("long", "put", 495, 0.12, 0.46, 0.54, 0.20),
    ]


def good_proposal(**kw):
    base = dict(symbol="SPY", structure="credit_spread", dte=14, legs=good_legs(), qty=1)
    base.update(kw)
    return ProposalView(**base)


def book(**kw):
    base = dict(nav=100_000)
    base.update(kw)
    return PortfolioView(**base)


def test_approve():
    v = validate(good_proposal(), book(), Settings())
    assert isinstance(v, Approve)


def test_veto_universe():
    assert validate(good_proposal(symbol="NVDA"), book(), Settings()).reason == "universe"


def test_discover_mode_allows_optionable_name(monkeypatch):
    from strategy import universe as uni

    uni.clear_universe_cache()
    monkeypatch.setattr(uni, "fetch_most_actives", lambda **_k: ["NVDA"])
    monkeypatch.setattr(uni, "fetch_movers", lambda **_k: [])
    monkeypatch.setattr(uni, "asset_optionable", lambda sym, **_k: True)
    monkeypatch.setattr(uni, "last_prices", lambda _syms, **_k: {s: 50.0 for s in _syms})
    s = Settings(universe_mode="discover", universe_size=4)
    assert isinstance(validate(good_proposal(symbol="NVDA"), book(), s), Approve)
    assert validate(good_proposal(symbol="SPY"), book(), s).reason == "universe"


def test_veto_dte():
    assert validate(good_proposal(dte=6), book(), Settings()).reason == "dte"
    assert validate(good_proposal(dte=22), book(), Settings()).reason == "dte"


def test_veto_delta():
    legs = good_legs()
    legs[0] = Leg("short", "put", 500, 0.40, 1.4, 1.6, 0.18)
    assert validate(good_proposal(legs=legs), book(), Settings()).reason == "short_delta"


def test_veto_max_loss_ignores_est():
    p = good_proposal(est_max_loss=1.0)
    # force huge width
    p.legs[1] = Leg("long", "put", 100, 0.12, 0.46, 0.54, 0.20)
    assert computed_max_loss(p) > 0.02 * 100_000
    assert validate(p, book(), Settings()).reason == "max_loss"


def test_other_vetoes():
    s = Settings()
    assert validate(good_proposal(), book(open_count=3), s).reason == "open_count"
    assert validate(good_proposal(), book(per_underlying={"SPY": 2}), s).reason == "per_underlying"
    assert validate(good_proposal(), book(overlapping_short=True), s).reason == "overlap"
    assert validate(good_proposal(), book(daily_halt=True), s).reason == "daily_halt"
    assert validate(good_proposal(), book(total_halt=True), s).reason == "total_halt"
    assert validate(good_proposal(), book(killed=True), s).reason == "kill_switch"
    assert validate(good_proposal(), book(cooldown=True), s).reason == "cooldown"
    assert validate(good_proposal(event_in_life=True), book(), s).reason == "event_risk"
    wide = good_legs()
    wide[0] = Leg("short", "put", 500, 0.25, 1.0, 2.0, 0.18)
    assert validate(good_proposal(legs=wide), book(), s).reason == "bid_ask"
    iv = good_legs()
    iv[0] = Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.01)
    assert validate(good_proposal(legs=iv), book(), s).reason == "iv"
    assert validate(good_proposal(structure="iron_condor"), book(), s).reason == "structure"


def test_veto_mismatched_rights():
    legs = [
        Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.18),
        Leg("long", "call", 505, 0.12, 0.46, 0.54, 0.20),
    ]
    assert validate(good_proposal(legs=legs), book(), Settings()).reason == "rights"


def test_veto_put_geometry():
    legs = [
        Leg("short", "put", 495, 0.25, 1.4, 1.6, 0.18),
        Leg("long", "put", 500, 0.12, 0.46, 0.54, 0.20),
    ]
    assert validate(good_proposal(legs=legs), book(), Settings()).reason == "geometry"


def test_veto_call_geometry():
    legs = [
        Leg("short", "call", 510, 0.25, 1.4, 1.6, 0.18),
        Leg("long", "call", 505, 0.12, 0.46, 0.54, 0.20),
    ]
    assert validate(good_proposal(legs=legs), book(), Settings()).reason == "geometry"


def test_veto_qty_and_credit():
    assert validate(good_proposal(qty=0), book(), Settings()).reason == "qty"
    debit = [
        Leg("short", "put", 500, 0.25, 0.4, 0.6, 0.18),
        Leg("long", "put", 495, 0.12, 1.4, 1.6, 0.20),
    ]
    assert validate(good_proposal(legs=debit), book(), Settings()).reason == "credit"


def test_veto_long_quote_and_liquidity():
    legs = [
        Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.18),
        Leg("long", "put", 495, 0.12, 0.0, 0.0, 0.20),
    ]
    assert validate(good_proposal(legs=legs), book(), Settings()).reason == "long_quote"
    wide_long = [
        Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.18),
        Leg("long", "put", 495, 0.12, 0.10, 0.90, 0.20),
    ]
    assert validate(good_proposal(legs=wide_long), book(), Settings()).reason == "bid_ask"
