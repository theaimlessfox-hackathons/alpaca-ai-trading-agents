from datetime import date

from strategy.chain import (
    bind_proposal,
    candidate_summary,
    has_viable_structure,
    in_band,
    long_candidates,
    parse_chain_response,
    short_candidates,
    slice_for_proposer,
)

TODAY = date(2026, 8, 31)


def snapshots_dict():
    return {
        "snapshots": {
            # good short put candidate: DTE 18, delta 0.25, tight spread, sane IV
            "SPY   260918P00500000": {
                "strike_price": 500,
                "expiration_date": "2026-09-18",
                "type": "put",
                "greeks": {"delta": -0.25},
                "latestQuote": {"bp": 1.4, "ap": 1.6},
                "impliedVolatility": 0.18,
            },
            # good long put candidate: same expiration, delta 0.12
            "SPY   260918P00495000": {
                "strike_price": 495,
                "expiration_date": "2026-09-18",
                "type": "put",
                "greeks": {"delta": -0.12},
                "latestQuote": {"bp": 0.46, "ap": 0.54},
                "impliedVolatility": 0.20,
            },
            # too close to expiry (DTE 3) -- must be dropped
            "SPY   260903P00510000": {
                "strike_price": 510,
                "expiration_date": "2026-09-03",
                "type": "put",
                "greeks": {"delta": -0.25},
                "latestQuote": {"bp": 1.4, "ap": 1.6},
                "impliedVolatility": 0.18,
            },
            # wide bid-ask -- must be dropped
            "SPY   260918P00480000": {
                "strike_price": 480,
                "expiration_date": "2026-09-18",
                "type": "put",
                "greeks": {"delta": -0.22},
                "latestQuote": {"bp": 0.10, "ap": 0.90},
                "impliedVolatility": 0.18,
            },
            # junk IV -- must be dropped
            "SPY   260918P00470000": {
                "strike_price": 470,
                "expiration_date": "2026-09-18",
                "type": "put",
                "greeks": {"delta": -0.24},
                "latestQuote": {"bp": 1.0, "ap": 1.1},
                "impliedVolatility": 5.0,
            },
            # missing delta -- must be skipped, not crash
            "SPY   260918P00460000": {
                "strike_price": 460,
                "expiration_date": "2026-09-18",
                "type": "put",
                "latestQuote": {"bp": 1.0, "ap": 1.1},
                "impliedVolatility": 0.18,
            },
        }
    }


def test_parse_skips_incomplete_and_keeps_valid():
    contracts = parse_chain_response(snapshots_dict(), today=TODAY)
    # 5 of 6 have enough fields (one missing delta is dropped)
    assert len(contracts) == 5
    by_strike = {c.strike: c for c in contracts}
    assert by_strike[500.0].dte == 18
    assert by_strike[500.0].right == "put"
    assert by_strike[500.0].delta == -0.25


def test_in_band_drops_dte_bidask_and_iv_outliers():
    contracts = parse_chain_response(snapshots_dict(), today=TODAY)
    banded = in_band(contracts)
    strikes = {c.strike for c in banded}
    assert 500.0 in strikes
    assert 495.0 in strikes
    assert all(7 <= c.dte <= 21 for c in banded)
    assert 480.0 not in strikes  # wide bid-ask
    assert 470.0 not in strikes  # junk IV
    dtes = sorted(c.dte for c in banded)
    assert 3 not in dtes  # the near-expiry contract at strike 500/DTE3 is excluded


def test_short_and_long_delta_bands():
    contracts = in_band(parse_chain_response(snapshots_dict(), today=TODAY))
    shorts = short_candidates(contracts)
    longs = long_candidates(contracts)
    assert any(abs(c.delta) == 0.25 for c in shorts)
    assert any(abs(c.delta) == 0.12 for c in longs)
    assert not any(abs(c.delta) == 0.12 for c in shorts)


def test_slice_for_proposer_end_to_end_has_viable_pair():
    sliced = slice_for_proposer(snapshots_dict(), today=TODAY)
    assert sliced["short_candidates"]
    assert sliced["long_candidates"]
    assert has_viable_structure(sliced)


def test_no_viable_structure_when_only_shorts_survive():
    raw = {
        "snapshots": {
            "SPY   260918P00500000": {
                "strike_price": 500,
                "expiration_date": "2026-09-18",
                "type": "put",
                "greeks": {"delta": -0.25},
                "latestQuote": {"bp": 1.4, "ap": 1.6},
                "impliedVolatility": 0.18,
            }
        }
    }
    sliced = slice_for_proposer(raw, today=TODAY)
    assert sliced["short_candidates"]
    assert not sliced["long_candidates"]
    assert has_viable_structure(sliced) is False


def test_no_viable_structure_on_empty_chain():
    assert has_viable_structure(slice_for_proposer({"snapshots": {}}, today=TODAY)) is False


def test_candidate_summary_is_json_serializable():
    contracts = in_band(parse_chain_response(snapshots_dict(), today=TODAY))
    rows = candidate_summary(contracts)
    assert all(isinstance(r["expiration"], str) for r in rows)
    import json

    json.dumps(rows)  # must not raise


def test_parse_falls_back_to_occ_expiration_when_field_missing():
    raw = {
        "snapshots": {
            "SPY   260918P00500000": {
                "strike_price": 500,
                "type": "put",
                "greeks": {"delta": -0.25},
                "latestQuote": {"bp": 1.4, "ap": 1.6},
                "impliedVolatility": 0.18,
            }
        }
    }
    contracts = parse_chain_response(raw, today=TODAY)
    assert len(contracts) == 1
    assert contracts[0].expiration == date(2026, 9, 18)


def test_parse_derives_delta_and_iv_via_black_scholes_when_missing():
    """Confirmed live: this feed never returns greeks/IV. Given spot, missing
    delta/iv must be derived from the mid quote, not skipped."""
    from strategy.blackscholes import bs_price

    spot = 500.0
    true_iv = 0.20
    dte = 14
    price = bs_price(spot, 500, dte / 365, true_iv, right="put")
    raw = {
        "snapshots": {
            "SPY260914P00500000": {
                "strike_price": 500,
                "expiration_date": "2026-09-14",
                "type": "put",
                "latestQuote": {"bp": round(price - 0.01, 2), "ap": round(price + 0.01, 2)},
                # no greeks, no impliedVolatility -- matches the live shape
            }
        }
    }
    contracts = parse_chain_response(raw, today=TODAY, spot=spot)
    assert len(contracts) == 1
    c = contracts[0]
    assert abs(c.iv - true_iv) < 0.01
    assert c.delta < 0  # put delta is negative
    assert -0.60 < c.delta < -0.40  # roughly ATM


def test_parse_skips_missing_greeks_without_spot():
    raw = {
        "snapshots": {
            "SPY260918P00500000": {
                "strike_price": 500,
                "expiration_date": "2026-09-18",
                "type": "put",
                "latestQuote": {"bp": 1.4, "ap": 1.6},
            }
        }
    }
    assert parse_chain_response(raw, today=TODAY, spot=None) == []


def test_slice_for_proposer_works_with_no_greeks_when_spot_given():
    from strategy.blackscholes import bs_price

    spot = 500.0
    price_short = bs_price(spot, 490, 14 / 365, 0.20, right="put")  # delta ~-0.28
    price_long = bs_price(spot, 480, 14 / 365, 0.20, right="put")  # delta ~-0.14
    raw = {
        "snapshots": {
            "SPY260914P00490000": {
                "strike_price": 490,
                "expiration_date": "2026-09-14",
                "type": "put",
                "latestQuote": {"bp": round(price_short - 0.02, 2), "ap": round(price_short + 0.02, 2)},
            },
            "SPY260914P00480000": {
                "strike_price": 480,
                "expiration_date": "2026-09-14",
                "type": "put",
                "latestQuote": {"bp": round(price_long - 0.02, 2), "ap": round(price_long + 0.02, 2)},
            },
        }
    }
    sliced = slice_for_proposer(raw, today=TODAY, spot=spot)
    assert has_viable_structure(sliced)


def test_bind_proposal_overwrites_model_fields():
    from agents.schemas import TradeProposal

    sliced = slice_for_proposer(snapshots_dict(), today=TODAY)
    invented = TradeProposal.model_validate(
        {
            "symbol": "SPY",
            "structure": "credit_spread",
            "expiration": "2026-09-18",
            "dte": 14,
            "legs": [
                {"side": "short", "right": "put", "strike": 500, "delta": 0.99, "bid": 9, "ask": 9.5, "iv": 0.9},
                {"side": "long", "right": "put", "strike": 495, "delta": 0.01, "bid": 0.01, "ask": 0.02, "iv": 0.9},
            ],
            "thesis": "t",
            "confidence": 0.5,
        }
    )
    bound = bind_proposal(invented, sliced)
    assert bound is not None
    assert bound.legs[0].bid == 1.4
    assert bound.legs[0].delta == -0.25
    assert bound.legs[0].occ_symbol
    missing = invented.model_copy(update={"expiration": "2026-12-18"})
    assert bind_proposal(missing, sliced) is None


def test_parse_handles_list_shape():
    raw = [
        {
            "symbol": "SPY   260918P00500000",
            "strike_price": 500,
            "expiration_date": "2026-09-18",
            "type": "put",
            "greeks": {"delta": -0.25},
            "latestQuote": {"bp": 1.4, "ap": 1.6},
            "impliedVolatility": 0.18,
        }
    ]
    contracts = parse_chain_response(raw, today=TODAY)
    assert len(contracts) == 1
