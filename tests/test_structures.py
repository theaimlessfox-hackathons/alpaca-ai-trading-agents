from datetime import date

import pytest

from risk.engine import Leg, ProposalView
from strategy.structures import close_mleg_payload, occ_symbol, to_mleg_payload


def proposal():
    return ProposalView(
        symbol="SPY",
        structure="credit_spread",
        dte=14,
        legs=[
            Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.18),
            Leg("long", "put", 495, 0.12, 0.46, 0.54, 0.20),
        ],
    )


def test_occ_format():
    # unpadded -- confirmed live against a real get_option_chain response
    assert occ_symbol("SPY", date(2026, 9, 18), "put", 500) == "SPY260918P00500000"


def test_two_legs_match_live_schema():
    p = to_mleg_payload(proposal(), client_order_id="e1", expiration=date(2026, 9, 18))
    assert p["order_class"] == "mleg"
    assert p["qty"] == "1"
    assert p["time_in_force"] == "day"
    assert "symbol" not in p  # parent symbol is single-leg only
    assert len(p["legs"]) == 2
    for lg in p["legs"]:
        assert "symbol" in lg and "ratio_qty" in lg
        assert isinstance(lg["ratio_qty"], str)
        assert len(lg["symbol"]) == 18  # SPY + YYMMDD + C/P + 8-digit strike, unpadded
    assert p["limit_price"].startswith("-")  # credit
    # natural = short bid 1.4 − long ask 0.54 = 0.86, not mid 1.00
    assert p["limit_price"] == "-0.86"


def test_entry_credit_uses_natural_then_mid_haircut():
    from strategy.structures import entry_credit

    legs = proposal().legs
    assert abs(entry_credit(legs) - 0.86) < 1e-9
    crossed = [
        Leg("short", "put", 500, 0.25, 0.40, 0.60, 0.18),
        Leg("long", "put", 495, 0.12, 0.46, 0.54, 0.20),
    ]
    # natural 0.40-0.54 < 0; mid = 0.50-0.50 = 0 → 0
    assert entry_credit(crossed) == 0.0
    wide_mid = [
        Leg("short", "put", 500, 0.25, 0.90, 1.50, 0.18),
        Leg("long", "put", 495, 0.12, 0.40, 1.00, 0.20),
    ]
    # natural 0.90-1.00 < 0; mid = 1.20-0.70 = 0.50 → 0.35
    assert abs(entry_credit(wide_mid) - 0.35) < 1e-9


def test_reject_condor():
    pr = proposal()
    pr.structure = "iron_condor"
    with pytest.raises(ValueError):
        to_mleg_payload(pr, client_order_id="x", expiration=date(2026, 9, 18))


def test_reject_one_leg():
    pr = proposal()
    pr.legs = pr.legs[:1]
    with pytest.raises(ValueError):
        to_mleg_payload(pr, client_order_id="x", expiration=date(2026, 9, 18))


def test_expiration_required():
    with pytest.raises(ValueError, match="expiration"):
        to_mleg_payload(proposal(), client_order_id="x")


def test_payload_uses_proposal_expiration():
    p = proposal()
    p.expiration = "2026-10-16"
    out = to_mleg_payload(p, client_order_id="e1")
    assert "261016" in out["legs"][0]["symbol"]


def test_close_is_atomic():
    open_p = to_mleg_payload(proposal(), client_order_id="e1", expiration=date(2026, 9, 18))
    close = close_mleg_payload(open_p, client_order_id="c1")
    assert len(close["legs"]) == 2
    with pytest.raises(ValueError):
        close_mleg_payload({"qty": "1", "legs": [open_p["legs"][0]]}, client_order_id="bad")


def test_close_limit_is_debit_not_copied_credit():
    open_p = to_mleg_payload(proposal(), client_order_id="e1", expiration=date(2026, 9, 18))
    assert open_p["limit_price"].startswith("-")
    close = close_mleg_payload(open_p, client_order_id="c1")
    assert float(close["limit_price"]) > 0
    assert close["limit_price"] != open_p["limit_price"]


def test_close_limit_uses_conservative_quotes():
    open_p = to_mleg_payload(proposal(), client_order_id="e1", expiration=date(2026, 9, 18))
    short_occ = open_p["legs"][0]["symbol"]
    long_occ = open_p["legs"][1]["symbol"]
    quotes = {short_occ: (1.2, 1.5), long_occ: (0.40, 0.50)}
    close = close_mleg_payload(open_p, client_order_id="c1", quotes=quotes)
    # buy short at 1.5 ask, sell long at 0.40 bid → debit 1.10
    assert close["limit_price"] == "1.10"


def test_close_qty_can_be_overridden():
    open_p = to_mleg_payload(proposal(), client_order_id="e1", expiration=date(2026, 9, 18))
    assert open_p["qty"] == "1"
    close = close_mleg_payload(open_p, client_order_id="c1", qty=2)
    assert close["qty"] == "2"


def test_close_qty_accepts_whole_number_decimal_string():
    open_p = to_mleg_payload(proposal(), client_order_id="e1", expiration=date(2026, 9, 18))
    close = close_mleg_payload(open_p, client_order_id="c1", qty="1.0")
    assert close["qty"] == "1"
