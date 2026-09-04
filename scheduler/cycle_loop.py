"""20–30 min name cycle. Sleeps when closed. --once for one pass."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from config.settings import get_settings
from config.states import StructureStatus
from execution.cancel import cancel_stale_entries
from execution.executor import dry_run
from execution.exit_policy import evaluate_exits
from execution.marks import mark_from_live_quotes
from execution.reconcile import reconcile_working
from execution.recover import recover_startup
from risk.engine import PortfolioView
from risk.kill_switch import cooldown_active, is_killed
from scheduler.loop import snapshot_and_maybe_flatten
from scheduler.market_hours import is_market_open, is_watchlist_window
from storage.db import DEFAULT_PATH, confirmed_regime_exit, create_all, insert_cycle
from storage.ledger import (
    active_structures,
    get_entry_payload,
    latest_filled_close_ts,
    open_structures,
    pending_entries,
)
from strategy.signals import iter_universe


ET = ZoneInfo("America/New_York")


def _midday_refresh_due(scan: dict, now: datetime | None = None) -> bool:
    """True once after noon ET when the latest scan is still the morning list."""
    current = now.astimezone(ET) if now else datetime.now(ET)
    minutes = current.hour * 60 + current.minute
    if current.weekday() >= 5 or not ((12 * 60) <= minutes < (16 * 60)):
        return False
    try:
        scanned = datetime.fromisoformat(str(scan.get("ts") or ""))
    except ValueError:
        return True
    if scanned.tzinfo is None:
        scanned = scanned.replace(tzinfo=timezone.utc)
    scanned = scanned.astimezone(ET)
    return scanned.date() == current.date() and scanned.hour < 12


def universe(path: Path = DEFAULT_PATH, *, now: datetime | None = None) -> list[str]:
    """Return the morning list, with one persisted refresh after noon ET."""
    settings = get_settings()
    if settings.universe_mode == "pinned":
        return list(iter_universe(settings))

    from storage.db import latest_scan, record_scan, trading_session_date
    from strategy.universe import clear_universe_cache, set_session_universe

    day = trading_session_date(now) if now is not None else None
    existing = latest_scan(session_date=day, path=path)
    refresh = bool(existing and existing.get("symbols") and _midday_refresh_due(existing, now))
    if existing and existing.get("symbols") and not refresh:
        symbols = [str(sym).upper() for sym in existing["symbols"]]
        set_session_universe(symbols)
        return symbols

    if refresh:
        clear_universe_cache()
    symbols = list(iter_universe(settings))
    if symbols:
        record_scan(symbols, path=path, now=now)
        return symbols
    if existing and existing.get("symbols"):
        # A failed midday data call must not erase a valid morning watchlist.
        symbols = [str(sym).upper() for sym in existing["symbols"]]
        set_session_universe(symbols)
    return symbols


def _prefetch_scan_articles(symbols: list[str], path: Path) -> None:
    """Best-effort headlines for today's scan so the Research page is not empty
    when a name stands down before the proposer runs."""
    try:
        import asyncio

        from storage.db import list_articles, record_articles
        from strategy.universe import cached_news_items
        from tools.news_parse import news_items
        from tools.research_tools import get_news
    except Exception:  # noqa: BLE001
        return
    for sym in symbols:
        try:
            cached = cached_news_items(sym)
            if cached:
                record_articles(sym, cached, path=path)
                continue
            if list_articles(symbol=sym, path=path):
                continue
            raw = asyncio.run(get_news(sym))
            record_articles(sym, news_items(raw), path=path)
        except Exception:  # noqa: BLE001 - one name must not kill the pass
            continue


def fetch_account_equity() -> float | None:
    try:
        import asyncio

        from tools.account_tools import get_account_info

        info = asyncio.run(get_account_info())
        data = info.get("data", info) if isinstance(info, dict) else info
        if isinstance(data, dict):
            value = data.get("portfolio_value") or data.get("equity")
            if value is not None:
                return float(value)
    except Exception:  # noqa: BLE001 - caller decides whether a missing print is fatal
        return None
    return None


def resolve_equity(*, live: bool, equity_fn: Callable[[], float] | None, path: Path) -> float | None:
    """Live paper must not size against a fictional $100k NAV.

    Order: injected fn, live account, last snapshot. Only dry-run may default.
    """
    if equity_fn is not None:
        return equity_fn()
    acct = fetch_account_equity()
    if acct is not None:
        return acct
    # Live paper must not size new risk against a stale snapshot.
    if live:
        return None
    from storage.db import recent_equity

    rows = recent_equity(limit=1, path=path)
    if rows:
        return float(rows[0]["equity"])
    return 100_000.0


def _book(path: Path, nav: float, *, symbol: str | None = None) -> PortfolioView:
    # Capacity counts live exposure AND in-flight entries. CLOSING / NEEDS_REVIEW
    # still sit at Alpaca and must consume a slot.
    live = list(active_structures(path))
    pending = list(pending_entries(path))
    per: dict[str, int] = {}
    for _sid, sym, _st, _qty in live + pending:
        per[sym] = per.get(sym, 0) + 1
    return PortfolioView(
        nav=nav,
        open_count=len(live) + len(pending),
        per_underlying=per,
        killed=is_killed(),
        cooldown=cooldown_active(
            latest_filled_close_ts(symbol, path) if symbol else None,
            datetime.now(timezone.utc),
        ),
    )


def _regime_stand_down(symbol: str) -> str | None:
    try:
        from scripts.run_once import real_inputs
        from strategy.regime import StandDown, decide

        regime_kwargs, _sliced = real_inputs(symbol)
        gate = decide(**regime_kwargs)
    except Exception:  # noqa: BLE001 - a failed regime read must not block other exits
        return None
    if isinstance(gate, StandDown):
        return gate.reason
    return None


def run_once(
    *,
    live: bool = False,
    path: Path = DEFAULT_PATH,
    equity_fn: Callable[[], float] | None = None,
    cycle_fn: Callable[[str], object] | None = None,
    lookup_fn: Callable[[str], object] | None = None,
    mark_fn: Callable[[int, dict], float | None] | None = None,
    submit_fn=None,
    skip_agent: bool = False,
) -> dict:
    """One autonomous pass: recover, snapshot/flatten, agent, execute, reconcile, exits."""
    create_all(path)
    symbols = universe(path)
    summary: dict = {
        "candidates": symbols,
        "results": [],
        "blocked": False,
        "snapshot": None,
        "reconciled": 0,
        "exits": [],
    }
    # Live path only: unit tests inject cycle_fn and must not hit Alpaca news.
    if cycle_fn is None and not skip_agent:
        _prefetch_scan_articles(symbols, path=path)

    rec = recover_startup(path=path, lookup_fn=lookup_fn)
    if rec == "block_startup":
        summary["blocked"] = True
        return summary

    live_submit = submit_fn
    if live and live_submit is None:
        from execution.broker import place_option_order_sync

        live_submit = place_option_order_sync

    equity = resolve_equity(live=live, equity_fn=equity_fn, path=path)
    if equity is None:
        # Cached print is for emergency flatten / display only — not for sizing.
        from storage.db import recent_equity

        cached = recent_equity(limit=1, path=path)
        flatten_eq = float(cached[0]["equity"]) if cached else None
        if flatten_eq is not None and is_killed():
            snap = snapshot_and_maybe_flatten(
                equity=flatten_eq,
                sod=flatten_eq,
                start=flatten_eq,
                payloads={},
                path=path,
                submit_fn=live_submit,
                lookup_fn=lookup_fn,
            )
            summary["snapshot"] = snap
        summary["blocked"] = True
        summary["reason"] = "missing_account_equity"
        return summary
    # SOD is recomputed inside snapshot after inserting this print.
    snap = snapshot_and_maybe_flatten(
        equity=equity,
        sod=equity,
        start=equity,
        payloads={},
        path=path,
        submit_fn=live_submit,
        lookup_fn=lookup_fn,
    )
    summary["snapshot"] = snap
    if snap in {"kill", "daily_halt", "total_halt"}:
        return summary
    if isinstance(snap, str) and snap.endswith("flatten_incomplete"):
        summary["blocked"] = True
        summary["reason"] = snap
        return summary

    regime_by_symbol: dict[str, str | None] = {}

    if not skip_agent:
        from agents.cycle import CycleResult, run_cycle

        for symbol in symbols:
            if cycle_fn is not None:
                cycle = cycle_fn(symbol)
            else:
                try:
                    from scripts.run_once import real_inputs

                    regime_kwargs, sliced = real_inputs(symbol)
                    cycle = run_cycle(symbol, chain_fn=lambda _s, _sl=sliced: _sl, **regime_kwargs)
                except Exception as exc:  # noqa: BLE001 - one name must not kill the pass
                    insert_cycle(symbol, "data_fail", type(exc).__name__, path=path)
                    summary["results"].append({"symbol": symbol, "verdict": "data_fail", "reason": type(exc).__name__})
                    continue
            if not isinstance(cycle, CycleResult):
                continue
            regime_by_symbol[symbol] = cycle.reason if cycle.verdict == "stand_down" else None
            if cycle.proposal is None:
                insert_cycle(symbol, cycle.verdict, cycle.reason, path=path)
                summary["results"].append(
                    {"symbol": symbol, "verdict": cycle.verdict, "reason": cycle.reason, "submitted": False}
                )
                continue
            # Rebuild per symbol so a recently closed name cannot churn straight
            # back into another spread while unrelated symbols remain eligible.
            book = _book(path, equity, symbol=symbol)
            out = dry_run(cycle.proposal, book, live=live, db_path=path, critic=cycle.critic)
            summary["results"].append(
                {
                    "symbol": symbol,
                    "verdict": cycle.verdict,
                    "reason": out.get("reason") or cycle.reason,
                    "submitted": bool(out.get("submitted")),
                }
            )

    summary["reconciled"] = reconcile_working(path=path, lookup_fn=lookup_fn)
    summary["stale_canceled"] = cancel_stale_entries(path=path, lookup_fn=lookup_fn)

    quote_fn = mark_fn if mark_fn is not None else (lambda _sid, payload: mark_from_live_quotes(payload))

    for sid, sym, status, _qty in open_structures(path):
        if status != StructureStatus.OPEN.value:
            continue
        payload = get_entry_payload(sid, path)
        if not payload:
            continue
        try:
            credit = abs(float(payload.get("limit_price") or 0))
        except (TypeError, ValueError):
            credit = 0.0
        mark = quote_fn(sid, payload)
        if sym not in regime_by_symbol:
            regime_by_symbol[sym] = _regime_stand_down(sym)
        stand_down = regime_by_symbol.get(sym)
        confirmed_stand_down = confirmed_regime_exit(
            sid,
            stand_down,
            required=get_settings().regime_exit_confirmations,
            path=path,
        )
        if mark is None and not confirmed_stand_down:
            continue
        if mark is None:
            mark = credit
        def _close(sid_, payload_, **kw):
            from execution.close import close_structure

            return close_structure(
                sid_, payload_, path=path, submit_fn=kw.get("submit_fn", live_submit)
            )

        why = evaluate_exits(
            structure_id=sid,
            credit=credit,
            mark=mark,
            structure_status=status,
            regime_stand_down=confirmed_stand_down,
            open_payload=payload,
            close_fn=_close,
            submit_fn=live_submit,
        )
        if why:
            summary["exits"].append(
                {
                    "structure_id": sid,
                    "reason": why.trigger,
                    "submitted": why.submitted,
                    "detail": why.reason,
                    "client_order_id": why.client_order_id,
                }
            )
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument(
        "--live",
        action="store_true",
        help="submit approved proposals to paper (requires EXPECTED_ACCOUNT_ID)",
    )
    args = p.parse_args()
    s = get_settings()
    if args.once:
        summary = run_once(live=args.live)
        print(json.dumps({k: summary[k] for k in summary}, default=str))
        return 2 if summary.get("blocked") else 0
    prepared_watchlist_day = None
    while True:
        if is_killed() or is_market_open():
            summary = run_once(live=args.live)
            print(
                "cycle",
                summary.get("candidates"),
                "blocked",
                summary.get("blocked"),
                "snap",
                summary.get("snapshot"),
                "results",
                summary.get("results"),
                flush=True,
            )
            time.sleep(60 if is_killed() or not is_market_open() else s.cycle_minutes * 60)
        elif is_watchlist_window():
            day = datetime.now(timezone.utc).astimezone().date().isoformat()
            if prepared_watchlist_day != day:
                print("start_of_day_watchlist", universe(), flush=True)
                prepared_watchlist_day = day
            time.sleep(60)
        else:
            time.sleep(60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
