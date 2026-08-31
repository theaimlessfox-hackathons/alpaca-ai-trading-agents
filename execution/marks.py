"""Live mark of an open credit spread from option quotes. No order I/O."""

from __future__ import annotations

import asyncio
from typing import Any


def _first(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _quotes_from_snapshot(raw: Any) -> dict[str, tuple[float, float]]:
    snapshots: Any = raw
    if isinstance(raw, dict):
        snapshots = raw.get("snapshots", raw)
    if isinstance(snapshots, dict):
        items = list(snapshots.items())
    elif isinstance(snapshots, list):
        items = [(s.get("symbol") or s.get("occ_symbol"), s) for s in snapshots if isinstance(s, dict)]
    else:
        items = []
    out: dict[str, tuple[float, float]] = {}
    for occ, snap in items:
        if not occ or not isinstance(snap, dict):
            continue
        quote = snap.get("latestQuote") or snap.get("latest_quote") or {}
        bid = _first(quote.get("bp"), quote.get("bid_price"), quote.get("bid"), snap.get("bid"))
        ask = _first(quote.get("ap"), quote.get("ask_price"), quote.get("ask"), snap.get("ask"))
        try:
            if bid is None or ask is None:
                continue
            bid_f, ask_f = float(bid), float(ask)
        except (TypeError, ValueError):
            continue
        if bid_f <= 0 or ask_f <= 0:
            continue
        out[str(occ)] = (bid_f, ask_f)
    return out


def net_mark(payload: dict, quotes: dict[str, tuple[float, float]]) -> float | None:
    """Same sign convention as original credit: short mid minus long mid."""
    legs = payload.get("legs") or []
    if len(legs) != 2:
        return None
    net = 0.0
    for lg in legs:
        occ = lg.get("symbol")
        if not occ or occ not in quotes:
            return None
        bid, ask = quotes[occ]
        mid = (bid + ask) / 2
        net += mid if lg.get("side") == "sell" else -mid
    return net


def fetch_quotes(payload: dict) -> dict[str, tuple[float, float]]:
    symbols = [lg.get("symbol") for lg in (payload.get("legs") or []) if lg.get("symbol")]
    if len(symbols) != 2:
        return {}
    try:
        from tools.research_tools import get_option_snapshot

        raw = asyncio.run(get_option_snapshot([str(s) for s in symbols]))
    except Exception:  # noqa: BLE001 - missing quotes fail closed at the caller
        return {}
    return _quotes_from_snapshot(raw)


def conservative_close_debit(open_payload: dict, quotes: dict[str, tuple[float, float]]) -> float | None:
    """Executable debit to flatten: buy the short at ask, sell the long at bid."""
    legs = open_payload.get("legs") or []
    if len(legs) != 2:
        return None
    debit = 0.0
    for lg in legs:
        occ = lg.get("symbol")
        if not occ or occ not in quotes:
            return None
        bid, ask = quotes[occ]
        if lg.get("side") == "sell":
            debit += ask
        else:
            debit -= bid
    return debit


def mark_from_live_quotes(payload: dict) -> float | None:
    quotes = fetch_quotes(payload)
    if not quotes:
        return None
    return net_mark(payload, quotes)
