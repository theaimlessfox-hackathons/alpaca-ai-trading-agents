import json
from pathlib import Path

from agents.llm import smoke
from agents.proposer import _context_to_user, run_proposer
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


def test_prompt_excludes_all_banded_non_candidate_pool():
    text = _context_to_user(
        "SPY",
        {
            "iv_rv": 1.4,
            "short_candidates": [{"symbol": "SHORT"}],
            "long_candidates": [{"symbol": "LONG"}],
            "all_banded": [{"symbol": "ATM-ONLY"}],
        },
    )
    assert "SHORT" in text and "LONG" in text
    assert "all_banded" not in text and "ATM-ONLY" not in text


def test_proposer_fails_over_to_xai_after_invalid_schema(monkeypatch):
    monkeypatch.setenv("XAI_FALLBACK", "true")
    monkeypatch.setenv("XAI_API_KEY", "fake-xai")
    get_settings.cache_clear()
    monkeypatch.setattr("agents.llm.chat", lambda *_a, **_k: json.dumps({"ok": True}))
    monkeypatch.setattr("agents.llm._xai_chat", lambda *_a, **_k: json.dumps(VALID))
    p = run_proposer("SPY", {"atm_iv": 0.22, "rv_20": 0.12})
    assert isinstance(p, TradeProposal)
    assert p.symbol == "SPY"


def test_proposer_does_not_call_xai_when_fallback_off(monkeypatch):
    monkeypatch.setenv("XAI_FALLBACK", "false")
    get_settings.cache_clear()
    calls = {"n": 0}

    def fake_chat(*_a, **_k):
        calls["n"] += 1
        return json.dumps({"ok": True})

    def boom(*_a, **_k):
        raise AssertionError("must not call xAI when fallback is disabled")

    monkeypatch.setattr("agents.llm.chat", fake_chat)
    monkeypatch.setattr("agents.llm._xai_chat", boom)
    assert run_proposer("SPY", {}) is None
    assert calls["n"] == 3


def test_no_execution_imports():
    for rel in ("agents/proposer.py", "agents/cycle.py", "agents/llm.py"):
        text = Path(rel).read_text()
        assert "import execution" not in text
        assert "from execution" not in text
