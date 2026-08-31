"""Propose a credit spread from prefetched context. Never imports execution."""

from __future__ import annotations

import json
from typing import Any, Callable

from agents.prompts import PROPOSER_SYSTEM
from agents.schemas import TradeProposal, parse_and_retry


def _context_to_user(symbol: str, context: dict[str, Any]) -> str:
    return (
        f"Symbol {symbol}. Prefetched context JSON:\n"
        f"{json.dumps(context, default=str)}\n"
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

        return chat(messages, json_mode=True)

    try:
        return parse_and_retry(call)
    except Exception:
        return None
