from __future__ import annotations

PROPOSER_SYSTEM = """You propose one defined-risk credit spread on the given symbol only.
DTE 7-21. Short delta 0.20-0.30, long 0.10-0.15.

The user message includes short_candidates and long_candidates: real, currently
quoted contracts that already satisfy the DTE, delta, bid-ask, and IV filters.
Choose the short leg from short_candidates and the long leg from long_candidates
by copying their strike, delta, bid, ask, and iv exactly as given. Both legs must
share the same expiration. Do not invent a strike, delta, bid, ask, or iv that
does not appear in the provided candidate lists.

The user message may also include recent_cycles (what happened on this symbol's
last few cycles: vetoed with a reason, or proposed) and headlines (recent news,
for context only). Neither one overrides the regime gate or the locked bands --
use recent_cycles to avoid repeating a proposal that was just vetoed for a
specific reason (e.g. don't propose 0.34 delta again if that's why the last one
was rejected), and use headlines only as color for your thesis, never as a
reason to trade outside the delta/DTE/structure rules above.

Output a single TradeProposal JSON object. No markdown fences, no prose.
Required keys: symbol, structure, expiration, dte, legs, thesis, confidence.
legs must contain exactly two objects (short then long) with side, right,
strike, delta, bid, ask, iv copied from the candidate lists.
structure must be credit_spread. No iron condors. Do not switch underlyings.
Never mention order placement tools.
"""

CRITIC_SYSTEM = """One short paragraph challenging the proposal plus invalidation conditions.
Advisory only. You do not approve or place orders.
"""


def format_cycle_recap(rows: list[dict]) -> str:
    """Deterministic recap of recent cycles for one symbol -- prompt memory,
    not training (plans/Grok.md rules out a training loop this week). Oldest
    first so it reads chronologically; rows come from storage.db.recent_cycles,
    which is most-recent-first, so this reverses them."""
    if not rows:
        return "No prior cycles for this symbol yet."
    parts = []
    for row in reversed(rows):
        verdict, reason = row.get("verdict"), row.get("reason")
        if verdict == "approve_dry":
            parts.append("approved (dry run)")
        elif reason:
            parts.append(f"{verdict} ({reason})")
        else:
            parts.append(str(verdict))
    return "Last cycles for this symbol, oldest to newest: " + "; ".join(parts) + "."


def format_headlines(headlines: list[str]) -> str:
    """Plain, deterministic formatting -- no summarization, so nothing here can
    quietly change what the model reads into a headline."""
    if not headlines:
        return "No recent headlines."
    return "Recent headlines: " + " | ".join(headlines[:5])
