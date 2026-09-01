"""Propose a credit spread from prefetched context. Never imports execution."""

from __future__ import annotations

import json
from typing import Any, Callable

from agents.prompts import PROPOSER_SYSTEM
from agents.schemas import TradeProposal, parse_and_retry


def _context_to_user(symbol: str, context: dict[str, Any]) -> str:
    # all_banded is needed to compute ATM IV, but it is not a choice set for the
    # model. Sending it made live prompts 20K+ characters and materially delayed
    # the fallback provider. The proposer only needs the already-filtered pools.
    prompt_context = {k: v for k, v in context.items() if k != "all_banded"}
    return (
        f"Symbol {symbol}. Prefetched context JSON:\n"
        f"{json.dumps(prompt_context, default=str)}\n"
        "Return only a TradeProposal JSON object."
    )


def run_proposer(
    symbol: str,
    context: dict[str, Any],
    *,
    chat_fn: Callable[[list[dict[str, str]]], str] | None = None,
) -> TradeProposal | None:
    def call(err: str | None) -> str:
        messages = [
            {"role": "system", "content": PROPOSER_SYSTEM},
            {"role": "user", "content": _context_to_user(symbol, context)},
        ]
        if err:
            messages.append({"role": "user", "content": f"Previous output failed validation: {err}"})
        if chat_fn is not None:
            return chat_fn(messages)
        from agents.llm import chat
        from config.settings import get_settings

        # Featherless is primary. A personality / non-schema JSON object still
        # counts as a chat() success, so schema failures have to escalate here
        # or xAI never runs. First attempt stays on the cascade; retries go to
        # Grok when XAI_FALLBACK is on.
        s = get_settings()
        if err and s.xai_fallback and s.xai_api_key:
            from agents.llm import _xai_chat

            return _xai_chat(messages, json_mode=True)
        return chat(messages, json_mode=True)

    try:
        return parse_and_retry(call)
    except Exception:
        return None
