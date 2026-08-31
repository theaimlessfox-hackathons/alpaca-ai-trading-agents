from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from config.settings import get_settings


@dataclass(frozen=True)
class Trade:
    iv_rv: float


@dataclass(frozen=True)
class StandDown:
    reason: str


def iv_rv_ratio(atm_iv: float | None, rv_20: float | None) -> float | None:
    if atm_iv is None or rv_20 is None or rv_20 <= 0:
        return None
    return atm_iv / rv_20


def decide(
    *,
    atm_iv: float | None,
    rv_20: float | None,
    rv_bar_count: int,
    breakout: bool,
    settings=None,
) -> Trade | StandDown:
    s = settings or get_settings()
    if breakout:
        return StandDown("breakout")
    if atm_iv is None or rv_20 is None or rv_bar_count < 15:
        return StandDown("insufficient_data")
    ratio = iv_rv_ratio(atm_iv, rv_20)
    if ratio is None:
        return StandDown("insufficient_data")
    if ratio < s.iv_rv_rich_min:
        return StandDown("cheap_iv_rv")
    return Trade(iv_rv=ratio)


def _bar_close(bar: dict) -> float | None:
    v = bar.get("c") if "c" in bar else bar.get("close")
    return float(v) if v is not None else None


def _bar_high_low(bar: dict) -> tuple[float | None, float | None]:
    hi = bar.get("h") if "h" in bar else bar.get("high")
    lo = bar.get("l") if "l" in bar else bar.get("low")
    return (float(hi) if hi is not None else None, float(lo) if lo is not None else None)


def realized_vol_20(bars: list[dict], *, lookback_days: int | None = None, settings=None) -> tuple[float | None, int]:
    """Annualized realized vol from daily close-to-close log returns.

    Returns (rv, bar_count_used). Not IV rank -- no historical IV percentile is
    computed or stored anywhere; see plans/dazzling-soaring-eclipse.md for why.
    """
    s = settings or get_settings()
    n = lookback_days or s.rv_lookback_days
    closes = [c for c in (_bar_close(b) for b in bars) if c is not None and c > 0]
    closes = closes[-(n + 1) :]
    if len(closes) < 2:
        return None, 0
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    if len(rets) < 2:
        return None, len(rets)
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return (var**0.5) * (252**0.5), len(rets)


def detect_breakout(bars: list[dict], *, k: float = 1.5) -> bool:
    """True if the latest day's high-low range exceeds k x the average of the
    prior days' ranges -- a simple ATR-style breakout flag, not a training signal."""
    ranges: list[float] = []
    for b in bars:
        hi, lo = _bar_high_low(b)
        if hi is None or lo is None:
            continue
        ranges.append(hi - lo)
    if len(ranges) < 6:
        return False
    today_range = ranges[-1]
    prior = ranges[:-1]
    avg_prior = sum(prior) / len(prior)
    return avg_prior > 0 and today_range > k * avg_prior


def atm_iv_from_candidates(candidates: list[dict], spot: float | None) -> float | None:
    """Nearest-to-spot-strike IV among contracts already DTE/bid-ask/IV-sane filtered
    by strategy/chain.py. Not a fresh unfiltered chain lookup."""
    if not candidates or spot is None:
        return None
    nearest = min(candidates, key=lambda c: abs(c["strike"] - spot))
    iv = nearest.get("iv")
    return float(iv) if iv is not None else None


def spot_from_bars(bars: list[dict]) -> float | None:
    """Last daily close as a spot proxy -- avoids a separate quote/snapshot fetch."""
    for bar in reversed(bars):
        close = _bar_close(bar)
        if close is not None:
            return close
    return None


def compute_regime_inputs(
    sliced_chain: dict[str, list[dict]],
    bars: list[dict],
    *,
    settings=None,
) -> dict[str, Any]:
    """Real bars + real sliced chain -> the atm_iv/rv_20/rv_bar_count/breakout
    kwargs that decide() needs. Pure function of already-fetched data; the I/O
    (calling MCP for bars/chain) lives in the caller, e.g. scripts/run_once.py."""
    s = settings or get_settings()
    rv, bar_count = realized_vol_20(bars, settings=s)
    breakout = detect_breakout(bars)
    spot = spot_from_bars(bars)
    all_candidates = list(sliced_chain.get("all_banded") or [])
    if not all_candidates:
        all_candidates = list(sliced_chain.get("short_candidates") or []) + list(
            sliced_chain.get("long_candidates") or []
        )
    atm_iv = atm_iv_from_candidates(all_candidates, spot)
    return {"atm_iv": atm_iv, "rv_20": rv, "rv_bar_count": bar_count, "breakout": breakout}
