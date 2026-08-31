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
