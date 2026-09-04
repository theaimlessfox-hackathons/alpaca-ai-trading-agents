from strategy.universe import (
    clear_universe_cache,
    discover_universe,
    rank_candidates,
    rank_with_news,
)


def test_rank_candidates_actives_then_movers_deduped():
    assert rank_candidates(["nvda", "TSLA", "NVDA"], ["AMD", "tsla", "BRK/B", "GFAIW"]) == [
        "NVDA",
        "TSLA",
        "AMD",
    ]


def test_discover_skips_non_optionable_and_caps():
    clear_universe_cache()
    out = discover_universe(
        limit=2,
        fetch_actives=lambda: ["NVDA", "XYZ", "TSLA"],
        fetch_movers_fn=lambda: ["AMD"],
        optionable_fn=lambda sym: sym != "XYZ",
        prices_fn=lambda syms: {s: 50.0 for s in syms},
        news_fn=lambda _syms: [],
    )
    assert out == ["NVDA", "AMD"]


def test_discover_drops_cheap_prints():
    clear_universe_cache()
    out = discover_universe(
        limit=4,
        fetch_actives=lambda: ["NVDA", "PENNY"],
        fetch_movers_fn=lambda: [],
        optionable_fn=lambda _s: True,
        prices_fn=lambda _syms: {"NVDA": 180.0, "PENNY": 1.2},
        news_fn=lambda _syms: [],
    )
    assert out == ["NVDA"]


def test_discover_fail_closed_on_fetch_error():
    clear_universe_cache()

    def boom():
        raise RuntimeError("data api down")

    assert discover_universe(fetch_actives=boom, fetch_movers_fn=lambda: [], optionable_fn=lambda _s: True) == []


def test_discover_cache_avoids_second_fetch():
    clear_universe_cache()
    calls = {"n": 0}

    def actives():
        calls["n"] += 1
        return ["NVDA"]

    first = discover_universe(
        limit=1,
        now=100.0,
        fetch_actives=actives,
        fetch_movers_fn=lambda: [],
        optionable_fn=lambda _s: True,
        prices_fn=lambda _s: {"NVDA": 180.0},
        news_fn=lambda _syms: [],
    )
    second = discover_universe(
        limit=1,
        now=110.0,
        fetch_actives=actives,
        fetch_movers_fn=lambda: [],
        optionable_fn=lambda _s: True,
        prices_fn=lambda _s: {"NVDA": 180.0},
    )
    assert first == second == ["NVDA"]
    assert calls["n"] == 1


def test_recent_alpaca_news_can_promote_an_eligible_candidate():
    eligible = ["AAA", "BBB", "CCC"]
    articles = [
        {"headline": "one", "symbols": ["CCC"]},
        {"headline": "two", "symbols": ["CCC"]},
        {"headline": "three", "symbols": ["CCC"]},
    ]
    ranked = rank_with_news(eligible, eligible, [], articles)
    assert ranked[0] == "CCC"


def test_news_cannot_add_a_symbol_outside_the_eligible_pool():
    ranked = rank_with_news(
        ["AAA", "BBB"],
        ["AAA", "BBB"],
        [],
        [{"headline": "outside", "symbols": ["ZZZ"]}],
    )
    assert ranked == ["AAA", "BBB"]
