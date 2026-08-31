"""Filter the real option chain to the locked bands before any model sees it.

The proposer chooses among surviving real contracts; it never invents strikes.
This is what makes risk/engine.py's numeric gates (max loss, bid-ask, IV sanity)
mean anything -- without it those gates only ever check numbers the model made up.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from config.settings import get_settings
from strategy.blackscholes import iv_and_delta_from_price


@dataclass(frozen=True)
class Contract:
    occ_symbol: str
    right: str  # "put" | "call"
    strike: float
    expiration: date
    dte: int
    delta: float
    bid: float
    ask: float
    iv: float


def _first(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _right_from_occ(occ: str) -> str | None:
    for i, ch in enumerate(occ):
        if ch in "CP" and i >= 6:
            return "call" if ch == "C" else "put"
    return None


def _strike_from_occ(occ: str) -> float | None:
    tail = occ[-8:]
    if len(tail) != 8 or not tail.isdigit():
        return None
    return int(tail) / 1000.0


def _exp_from_occ(occ: str) -> date | None:
    for i, ch in enumerate(occ):
        if ch in "CP" and i >= 6:
            yymmdd = occ[i - 6 : i]
            try:
                return datetime.strptime(yymmdd, "%y%m%d").date()
            except ValueError:
                return None
    return None


def parse_chain_response(
    raw: Any,
    *,
    today: date | None = None,
    spot: float | None = None,
    risk_free_rate: float = 0.04,
) -> list[Contract]:
    """Normalize a get_option_chain / get_option_snapshot result into Contracts.

    Prefers a broker-supplied delta/IV if present. Confirmed live (Aug 30) that
    this account's feed never supplies either -- opra 403s ("OPRA agreement is
    not signed"), and the indicative feed it falls back to carries neither field
    -- so when spot is given, missing delta/IV are derived from the mid quote via
    Black-Scholes inversion (strategy/blackscholes.py) instead of being skipped.
    Without spot, a contract missing delta/IV is dropped rather than guessed.
    """
    today = today or date.today()
    snapshots: Any = raw
    if isinstance(raw, dict):
        snapshots = raw.get("snapshots", raw)

    if isinstance(snapshots, dict):
        items = list(snapshots.items())
    elif isinstance(snapshots, list):
        items = [(s.get("symbol") or s.get("occ_symbol"), s) for s in snapshots if isinstance(s, dict)]
    else:
        items = []

    out: list[Contract] = []
    for occ, snap in items:
        if not occ or not isinstance(snap, dict):
            continue
        greeks = snap.get("greeks") or {}
        quote = snap.get("latestQuote") or snap.get("latest_quote") or {}

        delta = _first(greeks.get("delta"), snap.get("delta"))
        bid = _first(quote.get("bp"), quote.get("bid_price"), quote.get("bid"), snap.get("bid"))
        ask = _first(quote.get("ap"), quote.get("ask_price"), quote.get("ask"), snap.get("ask"))
        iv = _first(snap.get("impliedVolatility"), snap.get("implied_volatility"), snap.get("iv"))
        # Confirmed live (Aug 30): real snapshots carry only dailyBar/greeks/
        # impliedVolatility/latestQuote/latestTrade/minuteBar/prevDailyBar --
        # strike/expiration/type are NOT separate fields, only encoded in the
        # contract symbol itself. The snap.get(...) lookups are for whichever
        # other shape (get_option_contract, a future API version) might supply
        # them directly; the OCC-derived value is what actually fires today.
        strike = _first(snap.get("strike_price"), snap.get("strike"), _strike_from_occ(occ))
        right = _first(snap.get("type"), snap.get("right"), _right_from_occ(occ))
        exp_raw = _first(snap.get("expiration_date"), snap.get("expiration"))

        if None in (bid, ask, strike, right):
            continue

        exp = None
        if isinstance(exp_raw, date):
            exp = exp_raw
        elif exp_raw:
            try:
                exp = datetime.strptime(str(exp_raw)[:10], "%Y-%m-%d").date()
            except ValueError:
                exp = None
        if exp is None:
            exp = _exp_from_occ(occ)
        if exp is None:
            continue

        try:
            strike_f, bid_f, ask_f = float(strike), float(bid), float(ask)
            right_s = str(right).lower()
            dte = (exp - today).days

            if delta is None or iv is None:
                if spot is None or bid_f <= 0 or ask_f <= 0:
                    continue
                mid = (bid_f + ask_f) / 2
                derived_iv, derived_delta = iv_and_delta_from_price(
                    mid, spot, strike_f, dte, right=right_s, r=risk_free_rate
                )
                if derived_iv is None or derived_delta is None:
                    continue
                delta = derived_delta if delta is None else delta
                iv = derived_iv if iv is None else iv

            out.append(
                Contract(
                    occ_symbol=occ,
                    right=right_s,
                    strike=strike_f,
                    expiration=exp,
                    dte=dte,
                    delta=float(delta),
                    bid=bid_f,
                    ask=ask_f,
                    iv=float(iv),
                )
            )
        except (TypeError, ValueError):
            continue
    return out


def in_band(contracts: list[Contract], *, settings=None) -> list[Contract]:
    """DTE band + sane bid/ask spread + sane IV. Delta band applied separately per leg role."""
    s = settings or get_settings()
    out = []
    for c in contracts:
        if not (s.dte_min <= c.dte <= s.dte_max):
            continue
        if c.bid <= 0 or c.ask <= 0 or c.ask < c.bid:
            continue
        mid = (c.bid + c.ask) / 2
        if mid <= 0 or (c.ask - c.bid) / mid > s.bid_ask_max_frac:
            continue
        if not (s.iv_sane_min <= c.iv <= s.iv_sane_max):
            continue
        out.append(c)
    return out


def short_candidates(contracts: list[Contract], *, settings=None) -> list[Contract]:
    s = settings or get_settings()
    return [c for c in contracts if s.short_delta_min <= abs(c.delta) <= s.short_delta_max]


def long_candidates(contracts: list[Contract], *, settings=None) -> list[Contract]:
    s = settings or get_settings()
    return [c for c in contracts if s.long_delta_min <= abs(c.delta) <= s.long_delta_max]


def candidate_summary(contracts: list[Contract]) -> list[dict]:
    """JSON-serializable short list to hand to the proposer."""
    return [
        {
            "symbol": c.occ_symbol,
            "right": c.right,
            "strike": c.strike,
            "expiration": c.expiration.isoformat(),
            "dte": c.dte,
            "delta": c.delta,
            "bid": c.bid,
            "ask": c.ask,
            "iv": c.iv,
        }
        for c in contracts
    ]


def slice_for_proposer(
    raw_chain: Any, *, settings=None, today: date | None = None, spot: float | None = None
) -> dict[str, list[dict]]:
    """Real chain -> {"short_candidates": [...], "long_candidates": [...]}.

    Empty on either side means no viable structure this cycle -- the caller should
    skip the proposer entirely rather than let it invent a spread from nothing.
    Pass spot so delta/IV can be derived via Black-Scholes when the broker didn't
    supply them (confirmed the normal case on this account's feed).
    """
    s = settings or get_settings()
    parsed = parse_chain_response(raw_chain, today=today, spot=spot, risk_free_rate=s.risk_free_rate)
    banded = in_band(parsed, settings=s)
    return {
        "short_candidates": candidate_summary(short_candidates(banded, settings=s)),
        "long_candidates": candidate_summary(long_candidates(banded, settings=s)),
        # Unfiltered-by-delta in-band contracts. ATM IV must sample these, not
        # the 0.10–0.30 delta short/long pools (those are systematically OTM).
        "all_banded": candidate_summary(banded),
    }


def _leg_matches_candidate(leg: Any, candidate: dict, expiration: str) -> bool:
    occ = getattr(leg, "occ_symbol", None)
    if occ and candidate.get("symbol") == occ:
        return True
    try:
        same_right = str(candidate.get("right", "")).lower() == str(leg.right).lower()
        same_strike = abs(float(candidate["strike"]) - float(leg.strike)) < 1e-9
        same_exp = str(candidate.get("expiration")) == str(expiration)
    except (TypeError, ValueError, KeyError):
        return False
    return same_right and same_strike and same_exp


def bind_proposal(proposal: Any, sliced: dict[str, list[dict]]) -> Any | None:
    """Replace model-editable contract fields with the matched candidate.

    Returns None when any leg is not an exact member of the source chain slice.
    Callers must treat that as a failed cycle, not a proposal to execute.
    """
    from agents.schemas import ProposalLeg, TradeProposal

    if not isinstance(proposal, TradeProposal):
        return None
    new_legs: list[ProposalLeg] = []
    last_exp = proposal.expiration
    last_dte = proposal.dte
    for lg in proposal.legs:
        pool = sliced.get("short_candidates") if lg.side == "short" else sliced.get("long_candidates")
        found = None
        for candidate in pool or []:
            if _leg_matches_candidate(lg, candidate, proposal.expiration):
                found = candidate
                break
        if found is None:
            return None
        try:
            new_legs.append(
                ProposalLeg(
                    side=lg.side,
                    right=str(found["right"]).lower(),
                    strike=float(found["strike"]),
                    delta=float(found["delta"]),
                    bid=float(found["bid"]),
                    ask=float(found["ask"]),
                    iv=float(found["iv"]),
                    occ_symbol=str(found["symbol"]),
                )
            )
            last_exp = str(found["expiration"])
            last_dte = int(found["dte"])
        except (KeyError, TypeError, ValueError):
            return None
    if len(new_legs) != 2:
        return None
    return proposal.model_copy(update={"legs": new_legs, "expiration": last_exp, "dte": last_dte})


def has_viable_structure(sliced: dict[str, list[dict]]) -> bool:
    """True only if at least one short+long pair share an expiration and right."""
    shorts = sliced.get("short_candidates") or []
    longs = sliced.get("long_candidates") or []
    if not shorts or not longs:
        return False
    long_keys = {(lg["expiration"], lg["right"]) for lg in longs}
    return any((s["expiration"], s["right"]) in long_keys for s in shorts)


def fetch_and_slice_chain(symbol: str, *, settings=None, today: date | None = None) -> dict[str, list[dict]]:
    """I/O entry point: real MCP calls -> sliced candidates. Not unit tested beyond
    structure -- the parsing/filtering logic above is what's covered offline.

    Fetches a few days of bars for a spot proxy (last close), then requests the
    chain pre-filtered by expiration (the locked DTE band) and strike (a window
    around spot). An unfiltered call returns an arbitrary page that isn't centered
    near spot at all -- confirmed live -- so this filtering is load-bearing, not
    an optimization.
    """
    from datetime import timedelta

    from strategy.regime import spot_from_bars
    from tools.research_tools import get_option_chain, get_stock_bars

    s = settings or get_settings()
    today = today or date.today()

    bars_raw = asyncio.run(get_stock_bars(symbol, days=5))
    bars = bars_raw.get("bars", bars_raw) if isinstance(bars_raw, dict) else bars_raw
    if isinstance(bars, dict):
        bars = next((v for v in bars.values() if isinstance(v, list)), [])
    spot = spot_from_bars(bars or [])

    kwargs: dict[str, Any] = {
        "expiration_date_gte": (today + timedelta(days=s.dte_min)).isoformat(),
        "expiration_date_lte": (today + timedelta(days=s.dte_max)).isoformat(),
    }
    if spot:
        kwargs["strike_price_gte"] = round(spot * 0.80, 2)
        kwargs["strike_price_lte"] = round(spot * 1.20, 2)

    raw = asyncio.run(get_option_chain(symbol, **kwargs))
    return slice_for_proposer(raw, settings=s, today=today, spot=spot)
