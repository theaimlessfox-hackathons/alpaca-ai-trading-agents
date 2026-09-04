"""Build a daily watchlist from Alpaca market data — not a hardcoded list.

Most-actives and movers form the candidate pool. Recent Alpaca news then boosts
names with a current catalyst. Every result is checked on the trading API for
an active, tradable, options-enabled asset. Discovery failure is empty (fail
closed), never SPY/QQQ/IWM.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

import httpx

from config.settings import get_settings

DATA_HOST = "https://data.alpaca.markets"
_CACHE: dict[str, Any] = {"ts": 0.0, "symbols": [], "news": {}}
_CACHE_TTL_S = 300.0
_MIN_PRICE = 10.0
_LEVERED = (
    " 2X",
    " 3X",
    "1.5X",
    "DIREXION",
    "GRANITESHARES",
    "PROSHARES ULTRA",
    "YIELDMAX",
    "MICROSECTORS",
)


def _headers() -> dict[str, str]:
    key, secret = get_settings().execution_credentials()
    if not key or not secret:
        raise RuntimeError("Alpaca credentials missing")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def _trading_host() -> str:
    return (os.environ.get("APCA_API_BASE_URL") or "https://paper-api.alpaca.markets").rstrip("/")


def fetch_most_actives(*, top: int = 40, client: httpx.Client | None = None) -> list[str]:
    http = client or httpx.Client(timeout=15.0)
    resp = http.get(
        f"{DATA_HOST}/v1beta1/screener/stocks/most-actives",
        params={"by": "volume", "top": top},
        headers=_headers(),
    )
    resp.raise_for_status()
    return _symbols_from_rows(resp.json().get("most_actives") or resp.json().get("actives") or [])


def fetch_movers(*, top: int = 10, client: httpx.Client | None = None) -> list[str]:
    http = client or httpx.Client(timeout=15.0)
    resp = http.get(
        f"{DATA_HOST}/v1beta1/screener/stocks/movers",
        params={"top": top},
        headers=_headers(),
    )
    resp.raise_for_status()
    data = resp.json()
    out: list[str] = []
    for key in ("gainers", "losers"):
        out.extend(_symbols_from_rows(data.get(key) or []))
    return out


def fetch_market_news(
    symbols: list[str], *, limit: int = 50, client: httpx.Client | None = None
) -> list[dict[str, Any]]:
    """Recent Alpaca news for the candidate pool in one read-only request."""
    if not symbols:
        return []
    http = client or httpx.Client(timeout=15.0)
    resp = http.get(
        f"{DATA_HOST}/v1beta1/news",
        params={"symbols": ",".join(symbols), "limit": min(max(limit, 1), 50), "sort": "desc"},
        headers=_headers(),
    )
    resp.raise_for_status()
    data = resp.json()
    rows = data.get("news", data) if isinstance(data, dict) else data
    return [row for row in rows or [] if isinstance(row, dict)]


def _symbols_from_rows(rows: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if isinstance(row, str) and row.strip():
            out.append(row.strip().upper())
        elif isinstance(row, dict):
            sym = row.get("symbol")
            if sym:
                out.append(str(sym).strip().upper())
    return out


def _looks_like_equity_root(symbol: str) -> bool:
    if not symbol or len(symbol) > 5:
        return False
    if any(ch in symbol for ch in "/: "):
        return False
    # 5-letter *W / *U / *R tape is almost always a warrant, unit, or right.
    if len(symbol) >= 5 and symbol[-1] in {"W", "U", "R"}:
        return False
    return symbol.replace(".", "").isalpha()


def asset_optionable(symbol: str, *, client: httpx.Client | None = None) -> bool:
    http = client or httpx.Client(timeout=10.0)
    resp = http.get(f"{_trading_host()}/v2/assets/{symbol}", headers=_headers())
    if resp.status_code != 200:
        return False
    asset = resp.json()
    if not isinstance(asset, dict):
        return False
    if asset.get("status") and str(asset.get("status")).lower() != "active":
        return False
    if asset.get("tradable") is False:
        return False
    exchange = str(asset.get("exchange") or "").upper()
    if exchange in {"OTC", "OTCBB", "PINK"}:
        return False
    name = str(asset.get("name") or "").upper()
    if "WARRANT" in name or " RIGHT" in name or name.endswith(" UNIT") or " UNITS" in name:
        return False
    if any(tok in name for tok in _LEVERED):
        return False
    if asset.get("options_enabled") is True:
        return True
    attrs = asset.get("attributes") or []
    if isinstance(attrs, list) and ("has_options" in attrs or "options_enabled" in attrs):
        return True
    return False


def last_prices(symbols: list[str], *, client: httpx.Client | None = None) -> dict[str, float]:
    if not symbols:
        return {}
    http = client or httpx.Client(timeout=15.0)
    resp = http.get(
        f"{DATA_HOST}/v2/stocks/snapshots",
        params={"symbols": ",".join(symbols)},
        headers=_headers(),
    )
    resp.raise_for_status()
    data = resp.json()
    blobs = data.get("snapshots", data) if isinstance(data, dict) else {}
    if not isinstance(blobs, dict):
        return {}
    out: dict[str, float] = {}
    for sym, snap in blobs.items():
        if not isinstance(snap, dict):
            continue
        trade = snap.get("latestTrade") or snap.get("latest_trade") or {}
        daily = snap.get("dailyBar") or snap.get("daily_bar") or {}
        px = trade.get("p") if isinstance(trade, dict) else None
        if px is None and isinstance(daily, dict):
            px = daily.get("c")
        try:
            if px is not None:
                out[str(sym).upper()] = float(px)
        except (TypeError, ValueError):
            continue
    return out


def rank_candidates(actives: list[str], movers: list[str]) -> list[str]:
    """Most-actives first (volume), then movers not already listed. Deduped."""
    seen: set[str] = set()
    ranked: list[str] = []
    for sym in actives + movers:
        name = (sym or "").strip().upper()
        if name in seen or not _looks_like_equity_root(name):
            continue
        seen.add(name)
        ranked.append(name)
    return ranked


def rank_with_news(
    eligible: list[str],
    actives: list[str],
    movers: list[str],
    articles: list[dict[str, Any]],
) -> list[str]:
    """Rank attention, not direction, using only Alpaca-derived evidence.

    Activity supplies the base rank. Movers receive more weight and up to five
    recent articles add a bounded catalyst boost. News never makes an ineligible
    symbol tradable and is not interpreted as bullish or bearish.
    """
    active_rank = {sym.upper(): i for i, sym in enumerate(actives)}
    mover_rank = {sym.upper(): i for i, sym in enumerate(movers)}
    news_count = {sym: 0 for sym in eligible}
    for article in articles:
        symbols = article.get("symbols") or []
        if isinstance(symbols, str):
            symbols = [symbols]
        for raw in symbols if isinstance(symbols, list) else []:
            sym = str(raw).upper()
            if sym in news_count:
                news_count[sym] += 1

    def score(sym: str) -> tuple[int, int]:
        activity = max(0, 40 - active_rank[sym]) if sym in active_rank else 0
        movement = 2 * max(0, 20 - mover_rank[sym]) if sym in mover_rank else 0
        catalyst = 8 * min(news_count.get(sym, 0), 5)
        # Earlier eligibility order is the deterministic final tie-breaker.
        return activity + movement + catalyst, -eligible.index(sym)

    return sorted(eligible, key=score, reverse=True)


def cached_news_items(symbol: str) -> list[dict[str, str]]:
    """Normalized headlines captured while building the current watchlist."""
    return list((_CACHE.get("news") or {}).get(symbol.upper(), []))


def set_session_universe(symbols: list[str]) -> None:
    """Restore a persisted daily watchlist into this process's validation cache."""
    _CACHE["ts"] = time.time()
    _CACHE["symbols"] = [str(symbol).upper() for symbol in symbols]
    _CACHE["news"] = {}


def discover_universe(
    *,
    limit: int | None = None,
    now: float | None = None,
    ttl_s: float = _CACHE_TTL_S,
    fetch_actives: Callable[[], list[str]] | None = None,
    fetch_movers_fn: Callable[[], list[str]] | None = None,
    optionable_fn: Callable[[str], bool] | None = None,
    prices_fn: Callable[[list[str]], dict[str, float]] | None = None,
    news_fn: Callable[[list[str]], list[dict[str, Any]]] | None = None,
) -> list[str]:
    s = get_settings()
    cap = limit if limit is not None else s.universe_size
    cap = max(1, min(int(cap), 20))
    ts = now if now is not None else time.time()
    cached = _CACHE.get("symbols") or []
    if cached and ts - float(_CACHE.get("ts") or 0) < ttl_s:
        return list(cached)[:cap]

    try:
        actives = fetch_actives() if fetch_actives is not None else fetch_most_actives()
        movers = fetch_movers_fn() if fetch_movers_fn is not None else fetch_movers()
        check = optionable_fn if optionable_fn is not None else asset_optionable
        ranked = rank_candidates(actives, movers)
        try:
            get_px = prices_fn if prices_fn is not None else last_prices
            prices = get_px(ranked[:40])
        except Exception:  # noqa: BLE001 - missing prints must not invent a universe
            prices = {}
        eligible: list[str] = []
        pool_size = min(40, max(20, cap * 2))
        for sym in ranked:
            if prices and prices.get(sym, 0) < _MIN_PRICE:
                continue
            if check(sym):
                eligible.append(sym)
            if len(eligible) >= pool_size:
                break
        try:
            get_news = news_fn if news_fn is not None else fetch_market_news
            articles = get_news(eligible)
        except Exception:  # noqa: BLE001 - activity rank remains a safe fallback
            articles = []
        picked = rank_with_news(eligible, actives, movers, articles)[:cap]

        from tools.news_parse import news_items

        by_symbol: dict[str, list[dict[str, str]]] = {}
        for sym in picked:
            rows = []
            for article in articles:
                article_symbols = article.get("symbols") or []
                if isinstance(article_symbols, str):
                    article_symbols = [article_symbols]
                if sym in {str(item).upper() for item in article_symbols}:
                    rows.append(article)
            by_symbol[sym] = news_items({"news": rows}, limit=5)
    except Exception:  # noqa: BLE001 - empty universe is the fail-closed outcome
        picked = []
        by_symbol = {}

    _CACHE["ts"] = ts
    _CACHE["symbols"] = list(picked)
    _CACHE["news"] = by_symbol
    return list(picked)


def clear_universe_cache() -> None:
    _CACHE["ts"] = 0.0
    _CACHE["symbols"] = []
    _CACHE["news"] = {}
