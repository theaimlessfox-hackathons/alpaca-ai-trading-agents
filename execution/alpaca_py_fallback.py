"""MLEG via alpaca-py. Only called by executor when FALLBACK_MLEG=true."""

from __future__ import annotations

from typing import Any


def build_mleg_request(payload: dict[str, Any]):
    legs_in = payload.get("legs") or []
    if len(legs_in) != 2:
        raise ValueError("fallback refuses non-2-leg close/entry")
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, OptionLegRequest

    legs = [
        OptionLegRequest(
            symbol=lg["symbol"],
            ratio_qty=lg.get("ratio_qty", "1"),
            side=OrderSide.SELL if lg.get("side") == "sell" else OrderSide.BUY,
        )
        for lg in legs_in
    ]
    common = dict(
        qty=payload.get("qty", "1"),
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.MLEG,
        legs=legs,
        client_order_id=payload.get("client_order_id"),
    )
    if payload.get("type") == "limit" and payload.get("limit_price") is not None:
        return LimitOrderRequest(limit_price=payload["limit_price"], **common)
    return MarketOrderRequest(**common)
