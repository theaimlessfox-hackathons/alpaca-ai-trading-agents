"""Map a credit spread to a live place_option_order payload. No broker I/O."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from risk.engine import ProposalView, credit

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "docs" / "mcp-schemas" / "place_option_order.json"


def occ_symbol(underlying: str, expiration: date, right: str, strike: float) -> str:
    """ROOT + YYMMDD + C/P + strike*1000 (8 digits), unpadded.

    Confirmed live (Aug 30) against a real get_option_chain response: Alpaca's
    contract symbols are NOT space-padded to a 6-char root (e.g. "SPY260908C00510000",
    18 chars for SPY) despite that being the raw OCC/OPRA standard. Space-padding
    here would almost certainly make place_option_order reject the symbol as
    unrecognized.
    """
    root = underlying.strip().upper()
    yymmdd = expiration.strftime("%y%m%d")
    cp = "C" if right.lower().startswith("c") else "P"
    strike_i = int(round(strike * 1000))
    return f"{root}{yymmdd}{cp}{strike_i:08d}"


def load_place_option_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def assert_payload_matches_schema(payload: dict[str, Any]) -> None:
    schema = load_place_option_schema()["inputSchema"]
    allowed = set(schema.get("properties", {}))
    extra = set(payload) - allowed
    if extra:
        raise ValueError(f"payload keys not in live schema: {sorted(extra)}")
    for req in schema.get("required", []):
        if req not in payload:
            raise ValueError(f"missing required {req}")
    legs = payload.get("legs") or []
    if len(legs) != 2:
        raise ValueError("mleg credit spread needs exactly 2 legs")
    for lg in legs:
        if "symbol" not in lg or "ratio_qty" not in lg:
            raise ValueError("each leg needs symbol and ratio_qty")
        if not isinstance(lg["ratio_qty"], str):
            raise ValueError("ratio_qty must be string")


def entry_credit(legs: list) -> float:
    """Fillable credit for an opening limit, not the mid.

    Mid is what risk uses to decide the trade is good. The natural
    (short bid − long ask) is what a resting day order can actually print.
    If the natural is non-positive, give 30% of mid back to the market
    rather than sit at a price that never fills.
    """
    short = next((lg for lg in legs if lg.side == "short"), None)
    long = next((lg for lg in legs if lg.side == "long"), None)
    mid = credit(list(legs))
    if short is not None and long is not None:
        try:
            natural = float(short.bid) - float(long.ask)
        except (TypeError, ValueError):
            natural = None
        if natural is not None and natural > 0:
            return natural
    if mid > 0:
        return mid * 0.70
    return mid


def to_mleg_payload(
    proposal: ProposalView,
    *,
    client_order_id: str,
    expiration: date | None = None,
) -> dict[str, Any]:
    if proposal.structure != "credit_spread" or len(proposal.legs) != 2:
        raise ValueError("only credit_spread with 2 legs")
    exp = expiration
    if exp is None and getattr(proposal, "expiration", None):
        exp = date.fromisoformat(str(proposal.expiration)[:10])
    if exp is None:
        raise ValueError("expiration required")
    legs = []
    for lg in proposal.legs:
        occ = getattr(lg, "occ_symbol", None) or occ_symbol(proposal.symbol, exp, lg.right, lg.strike)
        side = "sell" if lg.side == "short" else "buy"
        legs.append(
            {
                "symbol": occ,
                "ratio_qty": "1",
                "side": side,
                "position_intent": "sell_to_open" if lg.side == "short" else "buy_to_open",
            }
        )
    net = entry_credit(proposal.legs)
    # live schema: positive = debit, negative = credit
    payload = {
        "qty": str(proposal.qty),
        "type": "limit",
        "time_in_force": "day",
        "order_class": "mleg",
        "client_order_id": client_order_id,
        "limit_price": f"{-abs(net):.2f}" if net >= 0 else f"{net:.2f}",
        "legs": legs,
    }
    assert_payload_matches_schema(payload)
    return payload


def close_limit_price(
    open_payload: dict[str, Any],
    *,
    quotes: dict[str, tuple[float, float]] | None = None,
) -> str:
    """Closing a credit spread is a debit. Never copy the opening credit sign.

    Prefer a conservative executable debit (buy the short at ask, sell the long
    at bid). If quotes are missing, invert the opening credit so the close is
    at least the right side of the market (debit, not another credit).
    """
    if quotes:
        from execution.marks import conservative_close_debit

        debit = conservative_close_debit(open_payload, quotes)
        if debit is not None:
            return f"{debit:.2f}"
    raw = open_payload.get("limit_price")
    try:
        opened = float(raw)
    except (TypeError, ValueError):
        raise ValueError("cannot price close") from None
    return f"{abs(opened):.2f}"


def close_mleg_payload(
    open_payload: dict[str, Any],
    *,
    client_order_id: str,
    quotes: dict[str, tuple[float, float]] | None = None,
    limit_price: str | None = None,
    qty: str | float | int | None = None,
) -> dict[str, Any]:
    """Atomic close: flip each leg and reprice as a debit. Never emit a 1-leg payload."""
    legs_in = open_payload.get("legs") or []
    if len(legs_in) != 2:
        raise ValueError("refuse non-atomic close")
    legs = []
    for lg in legs_in:
        side = "buy" if lg.get("side") == "sell" else "sell"
        intent = "buy_to_close" if lg.get("side") == "sell" else "sell_to_close"
        legs.append({**lg, "side": side, "position_intent": intent})
    price = limit_price or close_limit_price(open_payload, quotes=quotes)
    if qty is None:
        qty_s = str(open_payload.get("qty") or "1")
    else:
        qty_f = float(qty)
        qty_s = str(int(qty_f)) if qty_f == int(qty_f) else str(qty_f)
    out = {**open_payload, "client_order_id": client_order_id, "legs": legs, "limit_price": price, "qty": qty_s}
    assert_payload_matches_schema(out)
    return out
