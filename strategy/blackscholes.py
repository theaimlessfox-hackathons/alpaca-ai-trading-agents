"""Black-Scholes pricing, delta, and implied-vol inversion.

Needed because live testing (Aug 30, sandbox account) confirmed
get_option_chain / get_option_snapshot return no greeks and no implied
volatility on this account: the opra feed 403s with "OPRA agreement is not
signed", and the free/indicative feed it falls back to carries neither field
at all. This was anticipated as a "back pocket" fallback during planning; it
turned out to be required, not optional. Delta and IV are derived from the
mid quote instead of trusted from the broker.
"""

from __future__ import annotations

import math

_SQRT_2PI = math.sqrt(2 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))


def bs_price(spot: float, strike: float, t_years: float, vol: float, *, right: str, r: float = 0.04) -> float:
    """European option price. Degenerates to intrinsic value at t=0 or vol=0."""
    intrinsic = max(0.0, (spot - strike) if right == "call" else (strike - spot))
    if t_years <= 0 or vol <= 0 or spot <= 0 or strike <= 0:
        return intrinsic
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * t_years) / (vol * math.sqrt(t_years))
    d2 = d1 - vol * math.sqrt(t_years)
    if right == "call":
        return spot * _norm_cdf(d1) - strike * math.exp(-r * t_years) * _norm_cdf(d2)
    return strike * math.exp(-r * t_years) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def bs_delta(spot: float, strike: float, t_years: float, vol: float, *, right: str, r: float = 0.04) -> float:
    if t_years <= 0 or vol <= 0 or spot <= 0 or strike <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * t_years) / (vol * math.sqrt(t_years))
    return _norm_cdf(d1) if right == "call" else _norm_cdf(d1) - 1.0


def implied_vol(
    price: float,
    spot: float,
    strike: float,
    t_years: float,
    *,
    right: str,
    r: float = 0.04,
    lo: float = 0.01,
    hi: float = 5.0,
    tol: float = 1e-4,
    max_iter: int = 100,
) -> float | None:
    """Bisection on volatility. Robust and derivative-free -- fine for a
    handful of contracts per cycle, not a performance-sensitive path.
    Returns None when the price is outside what [lo, hi] vol can reach
    (e.g. below intrinsic value, or a data glitch)."""
    if price <= 0 or t_years <= 0 or spot <= 0 or strike <= 0:
        return None
    intrinsic = max(0.0, (spot - strike) if right == "call" else (strike - spot))
    if price < intrinsic:
        return None
    f_lo = bs_price(spot, strike, t_years, lo, right=right, r=r) - price
    f_hi = bs_price(spot, strike, t_years, hi, right=right, r=r) - price
    if f_lo > 0 or f_hi < 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = bs_price(spot, strike, t_years, mid, right=right, r=r) - price
        if abs(f_mid) < tol:
            return mid
        if f_mid > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def iv_and_delta_from_price(
    mid_price: float,
    spot: float,
    strike: float,
    dte: int,
    *,
    right: str,
    r: float = 0.04,
) -> tuple[float | None, float | None]:
    """Given a mid quote and days-to-expiry, back out (iv, delta) together so
    they're internally consistent -- delta is computed from the same vol that
    reproduces the observed price, not a separately-guessed number."""
    t_years = dte / 365.0
    vol = implied_vol(mid_price, spot, strike, t_years, right=right, r=r)
    if vol is None:
        return None, None
    return vol, bs_delta(spot, strike, t_years, vol, right=right, r=r)
