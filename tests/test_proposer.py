import json
from pathlib import Path

from agents.llm import smoke
from agents.proposer import run_proposer
from agents.schemas import TradeProposal
from config.settings import get_settings


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


def test_smoke_missing_key():
    get_settings.cache_clear()
    r = smoke()
    if not get_settings().featherless_api_key:
        assert r.ok is False
        assert "FEATHERLESS" in (r.error or "")


def test_proposer_from_prefetched_context():
    p = run_proposer("SPY", {"atm_iv": 0.22, "rv_20": 0.12}, chat_fn=lambda _m: json.dumps(VALID))
    assert isinstance(p, TradeProposal)
    assert p.symbol == "SPY"


def test_proposer_parse_fail_returns_none():
    assert run_proposer("SPY", {}, chat_fn=lambda _m: "not-json") is None


def test_no_execution_imports():
    for rel in ("agents/proposer.py", "agents/cycle.py", "agents/llm.py"):
        text = Path(rel).read_text()
        assert "import execution" not in text
        assert "from execution" not in text
