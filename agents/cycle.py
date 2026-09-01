from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from agents.schemas import CriticNote, TradeProposal
from strategy.regime import StandDown, decide


@dataclass
class CycleResult:
    symbol: str
    proposal: TradeProposal | None
    verdict: str
    reason: str
    critic: CriticNote | None = None


def run_cycle(
    symbol: str,
    *,
    atm_iv: float | None,
    rv_20: float | None,
    rv_bar_count: int,
    breakout: bool,
    context: dict[str, Any] | None = None,
    propose_fn: Callable[..., TradeProposal | None] | None = None,
    chain_fn: Callable[[str], dict[str, list[dict[str, Any]]]] | None = None,
    recap_fn: Callable[[str], list[dict[str, Any]]] | None = None,
    news_fn: Callable[[str], list[str]] | None = None,
    critic_fn: Callable[[TradeProposal], CriticNote | None] | None = None,
) -> CycleResult:
    gate = decide(atm_iv=atm_iv, rv_20=rv_20, rv_bar_count=rv_bar_count, breakout=breakout)
    if isinstance(gate, StandDown):
        return CycleResult(symbol, None, "stand_down", gate.reason)

    def _chain(sym: str) -> dict[str, list[dict[str, Any]]]:
        if chain_fn is not None:
            return chain_fn(sym)
        from strategy.chain import fetch_and_slice_chain

        return fetch_and_slice_chain(sym)

    sliced = _chain(symbol)

    from strategy.chain import has_viable_structure

    if not has_viable_structure(sliced):
        return CycleResult(symbol, None, "no_candidates", "no_viable_contracts")

    def _recap(sym: str) -> list[dict[str, Any]]:
        if recap_fn is not None:
            return recap_fn(sym)
        try:
            from storage.db import recent_cycles

            return recent_cycles(sym)
        except Exception:  # noqa: BLE001 - prompt memory is best-effort, never blocks a cycle
            return []

    def _news(sym: str) -> list[str]:
        if news_fn is not None:
            return news_fn(sym)
        try:
            import asyncio

            from storage.db import record_articles
            from tools.news_parse import news_items
            from tools.research_tools import get_news

            # get_news's live response shape is unverified (unlike get_option_chain/
            # get_stock_bars, which were confirmed against a real call) -- defensive
            # about the key name for the same reason strategy/chain.py is.
            raw = asyncio.run(get_news(sym))
            items = news_items(raw)
            try:
                record_articles(sym, items)
            except Exception:  # noqa: BLE001 - research log must not block a cycle
                pass
            return [row["headline"] for row in items]
        except Exception:  # noqa: BLE001 - news is color, not a gate; never blocks a cycle
            return []

    def _propose(sym: str, _gate, _sliced: dict[str, list[dict[str, Any]]]) -> TradeProposal | None:
        if propose_fn is not None:
            return propose_fn(sym, _gate)
        from agents.prompts import format_cycle_recap, format_headlines
        from agents.proposer import run_proposer

        ctx = dict(context or {})
        ctx["iv_rv"] = getattr(_gate, "iv_rv", None)
        ctx.update(_sliced)
        ctx["recent_cycles"] = format_cycle_recap(_recap(sym))
        ctx["headlines"] = format_headlines(_news(sym))
        return run_proposer(sym, ctx)

    proposal = _propose(symbol, gate, sliced)
    if proposal is None:
        return CycleResult(symbol, None, "parse_fail", "invalid_json")

    from strategy.chain import bind_proposal

    bound = bind_proposal(proposal, sliced)
    if bound is None:
        return CycleResult(symbol, None, "bind_fail", "not_a_candidate")
    proposal = bound

    def _critic(prop: TradeProposal) -> CriticNote | None:
        # Advisory only -- a critic failure never blocks the cycle or changes the
        # verdict; the risk engine downstream is the only real veto. The
        # try/except wraps the injected critic_fn too, not just the default
        # path: a caller-supplied critic (e.g. simulating "Featherless down" in
        # a test) must fail safe exactly the same way the real one does.
        try:
            if critic_fn is not None:
                return critic_fn(prop)
            from agents.critic import run_critic
            from agents.llm import chat

            return run_critic(prop, chat_fn=lambda messages: chat(messages, json_mode=True))
        except Exception:  # noqa: BLE001 - advisory only, see above
            return None

    critic = _critic(proposal)
    return CycleResult(symbol, proposal, "proposed", "ok", critic=critic)
