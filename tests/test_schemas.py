import json

from agents.schemas import TradeProposal, parse_and_retry
from pydantic import ValidationError
import pytest

VALID = {
    "symbol": "SPY",
    "structure": "credit_spread",
    "expiration": "2026-09-18",
    "dte": 14,
    "legs": [
        {"side": "short", "right": "put", "strike": 500, "delta": 0.25, "bid": 1.4, "ask": 1.6, "iv": 0.18},
        {"side": "long", "right": "put", "strike": 495, "delta": 0.12, "bid": 0.46, "ask": 0.54, "iv": 0.2},
    ],
    "thesis": "rich iv/rv",
    "confidence": 0.6,
}


def test_valid():
    assert TradeProposal.model_validate(VALID).symbol == "SPY"


def test_missing_legs():
    bad = {**VALID, "legs": []}
    with pytest.raises(ValidationError):
        TradeProposal.model_validate(bad)


def test_condor_rejected():
    with pytest.raises(ValidationError):
        TradeProposal.model_validate({**VALID, "structure": "iron_condor"})


def test_retry_then_none():
    n = {"i": 0}

    def fn(_err):
        n["i"] += 1
        return "not-json"

    assert parse_and_retry(fn) is None
    assert n["i"] == 3


def test_retry_success():
    n = {"i": 0}

    def fn(_err):
        n["i"] += 1
        if n["i"] < 2:
            return "{"
        return json.dumps(VALID)

    p = parse_and_retry(fn)
    assert p is not None and n["i"] == 2


def test_retry_accepts_fenced_json():
    p = parse_and_retry(lambda _err: "```json\n" + json.dumps(VALID) + "\n```")
    assert p is not None and p.symbol == "SPY"


def test_retry_accepts_prose_wrapped_json():
    p = parse_and_retry(lambda _err: "Sure, here you go:\n" + json.dumps(VALID) + "\nGood luck.")
    assert p is not None and p.symbol == "SPY"


def test_retry_unwraps_nested_proposal():
    p = parse_and_retry(lambda _err: json.dumps({"proposal": VALID}))
    assert p is not None and p.symbol == "SPY"
