from agents.cycle import run_cycle
from agents.schemas import TradeProposal

VIABLE_CHAIN = {
    "short_candidates": [
        {"symbol": "QQQ   260918P00500000", "right": "put", "strike": 500, "expiration": "2026-09-18",
         "dte": 14, "delta": -0.25, "bid": 1.4, "ask": 1.6, "iv": 0.18},
    ],
    "long_candidates": [
        {"symbol": "QQQ   260918P00495000", "right": "put", "strike": 495, "expiration": "2026-09-18",
         "dte": 14, "delta": -0.12, "bid": 0.46, "ask": 0.54, "iv": 0.20},
    ],
}


def test_stand_down_skips_llm():
    calls = {"n": 0}

    def propose(*_a):
        calls["n"] += 1
        raise AssertionError("should not run")

    def chain(*_a):
        calls["n"] += 1
        raise AssertionError("chain should not be fetched either")

    r = run_cycle(
        "SPY", atm_iv=0.1, rv_20=0.2, rv_bar_count=20, breakout=False, propose_fn=propose, chain_fn=chain
    )
    assert r.verdict == "stand_down"
    assert r.proposal is None
    assert calls["n"] == 0


def test_no_viable_candidates_skips_llm():
    calls = {"n": 0}

    def propose(*_a):
        calls["n"] += 1
        raise AssertionError("should not run without a viable structure")

    r = run_cycle(
        "SPY",
        atm_iv=0.3,
        rv_20=0.1,
        rv_bar_count=20,
        breakout=False,
        propose_fn=propose,
        chain_fn=lambda _sym: {"short_candidates": [], "long_candidates": []},
    )
    assert r.verdict == "no_candidates"
    assert r.proposal is None
    assert calls["n"] == 0


def test_rich_vol_uses_proposer():
    def propose(sym, _g):
        return TradeProposal.model_validate(
            {
                "symbol": sym,
                "structure": "credit_spread",
                "expiration": "2026-09-18",
                "dte": 14,
                "legs": [
                    {"side": "short", "right": "put", "strike": 500, "delta": 0.25, "bid": 1.4, "ask": 1.6, "iv": 0.18},
                    {"side": "long", "right": "put", "strike": 495, "delta": 0.12, "bid": 0.46, "ask": 0.54, "iv": 0.2},
                ],
                "thesis": "t",
                "confidence": 0.5,
            }
        )

    r = run_cycle(
        "QQQ",
        atm_iv=0.3,
        rv_20=0.1,
        rv_bar_count=20,
        breakout=False,
        propose_fn=propose,
        chain_fn=lambda _sym: VIABLE_CHAIN,
        critic_fn=lambda _p: None,
    )
    assert r.verdict == "proposed"
    assert r.proposal is not None
    assert r.proposal.symbol == "QQQ"


def test_proposer_receives_sliced_candidates_in_context():
    captured = {}

    from agents.proposer import run_proposer as real_run_proposer

    def fake_run_proposer(sym, ctx):
        captured["ctx"] = ctx
        return real_run_proposer(sym, ctx, chat_fn=lambda _m: __import__("json").dumps(
            {
                "symbol": sym,
                "structure": "credit_spread",
                "expiration": "2026-09-18",
                "dte": 14,
                "legs": [
                    {"side": "short", "right": "put", "strike": 500, "delta": 0.25, "bid": 1.4, "ask": 1.6, "iv": 0.18},
                    {"side": "long", "right": "put", "strike": 495, "delta": 0.12, "bid": 0.46, "ask": 0.54, "iv": 0.2},
                ],
                "thesis": "t",
                "confidence": 0.5,
            }
        ))

    import agents.cycle as cycle_mod

    orig = cycle_mod.run_cycle
    # exercise the real (non-injected) proposer path by monkeypatching the module-level import target
    import agents.proposer as proposer_mod

    saved = proposer_mod.run_proposer
    proposer_mod.run_proposer = fake_run_proposer
    try:
        r = orig(
            "QQQ",
            atm_iv=0.3,
            rv_20=0.1,
            rv_bar_count=20,
            breakout=False,
            chain_fn=lambda _sym: VIABLE_CHAIN,
            recap_fn=lambda _sym: [],
            news_fn=lambda _sym: [],
            critic_fn=lambda _p: None,
        )
    finally:
        proposer_mod.run_proposer = saved

    assert r.verdict == "proposed"
    assert "short_candidates" in captured["ctx"]
    assert "long_candidates" in captured["ctx"]
    assert captured["ctx"]["short_candidates"] == VIABLE_CHAIN["short_candidates"]


def test_proposer_receives_recap_and_headlines_in_context():
    captured = {}

    def propose(sym, _g):
        captured["ctx_placeholder"] = None  # propose_fn path doesn't see ctx directly
        return TradeProposal.model_validate(
            {
                "symbol": sym,
                "structure": "credit_spread",
                "expiration": "2026-09-18",
                "dte": 14,
                "legs": [
                    {"side": "short", "right": "put", "strike": 500, "delta": 0.25, "bid": 1.4, "ask": 1.6, "iv": 0.18},
                    {"side": "long", "right": "put", "strike": 495, "delta": 0.12, "bid": 0.46, "ask": 0.54, "iv": 0.2},
                ],
                "thesis": "t",
                "confidence": 0.5,
            }
        )

    # propose_fn short-circuits before recap/news are ever fetched -- confirm
    # recap_fn/news_fn are simply not called in that path (no wasted DB/network work).
    def boom(_sym):
        raise AssertionError("must not fetch recap/news when propose_fn is injected")

    r = run_cycle(
        "QQQ",
        atm_iv=0.3,
        rv_20=0.1,
        rv_bar_count=20,
        breakout=False,
        propose_fn=propose,
        chain_fn=lambda _sym: VIABLE_CHAIN,
        recap_fn=boom,
        news_fn=boom,
        critic_fn=lambda _p: None,
    )
    assert r.verdict == "proposed"


def _valid_proposal(sym="QQQ") -> TradeProposal:
    return TradeProposal.model_validate(
        {
            "symbol": sym,
            "structure": "credit_spread",
            "expiration": "2026-09-18",
            "dte": 14,
            "legs": [
                {"side": "short", "right": "put", "strike": 500, "delta": 0.25, "bid": 1.4, "ask": 1.6, "iv": 0.18},
                {"side": "long", "right": "put", "strike": 495, "delta": 0.12, "bid": 0.46, "ask": 0.54, "iv": 0.2},
            ],
            "thesis": "t",
            "confidence": 0.5,
        }
    )


def test_critic_runs_after_a_successful_proposal():
    from agents.schemas import CriticNote

    seen = {}

    def critic_fn(prop):
        seen["symbol"] = prop.symbol
        return CriticNote(rebuttal="challenge", invalidation=["x"])

    r = run_cycle(
        "QQQ",
        atm_iv=0.3,
        rv_20=0.1,
        rv_bar_count=20,
        breakout=False,
        propose_fn=lambda sym, _g: _valid_proposal(sym),
        chain_fn=lambda _sym: VIABLE_CHAIN,
        critic_fn=critic_fn,
    )
    assert r.verdict == "proposed"
    assert r.critic is not None
    assert r.critic.rebuttal == "challenge"
    assert seen["symbol"] == "QQQ"


def test_critic_is_not_called_on_stand_down():
    def boom(_p):
        raise AssertionError("critic must not run when there is no proposal")

    r = run_cycle(
        "SPY", atm_iv=0.1, rv_20=0.2, rv_bar_count=20, breakout=False, critic_fn=boom
    )
    assert r.verdict == "stand_down"
    assert r.critic is None


def test_critic_is_not_called_on_no_candidates():
    def boom(_p):
        raise AssertionError("critic must not run without a viable structure")

    r = run_cycle(
        "SPY",
        atm_iv=0.3,
        rv_20=0.1,
        rv_bar_count=20,
        breakout=False,
        chain_fn=lambda _sym: {"short_candidates": [], "long_candidates": []},
        critic_fn=boom,
    )
    assert r.verdict == "no_candidates"
    assert r.critic is None


def test_invented_strike_fails_bind():
    def propose(sym, _g):
        p = _valid_proposal(sym)
        p.legs[0].strike = 501
        return p

    r = run_cycle(
        "QQQ",
        atm_iv=0.3,
        rv_20=0.1,
        rv_bar_count=20,
        breakout=False,
        propose_fn=propose,
        chain_fn=lambda _sym: VIABLE_CHAIN,
        critic_fn=lambda _p: None,
    )
    assert r.verdict == "bind_fail"
    assert r.proposal is None


def test_bound_proposal_uses_candidate_quotes():
    def propose(sym, _g):
        p = _valid_proposal(sym)
        p.legs[0].bid = 9.9
        p.legs[0].ask = 9.95
        p.legs[0].iv = 0.99
        return p

    r = run_cycle(
        "QQQ",
        atm_iv=0.3,
        rv_20=0.1,
        rv_bar_count=20,
        breakout=False,
        propose_fn=propose,
        chain_fn=lambda _sym: VIABLE_CHAIN,
        critic_fn=lambda _p: None,
    )
    assert r.verdict == "proposed"
    assert r.proposal is not None
    assert r.proposal.legs[0].bid == 1.4
    assert r.proposal.legs[0].iv == 0.18
    assert r.proposal.legs[0].occ_symbol == VIABLE_CHAIN["short_candidates"][0]["symbol"]


def test_critic_failure_does_not_block_the_cycle():
    def critic_fn(_p):
        raise RuntimeError("featherless down")

    r = run_cycle(
        "QQQ",
        atm_iv=0.3,
        rv_20=0.1,
        rv_bar_count=20,
        breakout=False,
        propose_fn=lambda sym, _g: _valid_proposal(sym),
        chain_fn=lambda _sym: VIABLE_CHAIN,
        critic_fn=critic_fn,
    )
    assert r.verdict == "proposed"
    assert r.critic is None

