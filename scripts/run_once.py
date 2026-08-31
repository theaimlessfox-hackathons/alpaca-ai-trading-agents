#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.cycle import run_cycle
from agents.schemas import TradeProposal
from execution.executor import dry_run
from risk.engine import PortfolioView
from storage.db import create_all


def fixture_proposal(symbol: str) -> TradeProposal:
    return TradeProposal.model_validate(
        {
            "symbol": symbol,
            "structure": "credit_spread",
            "expiration": "2026-09-18",
            "dte": 14,
            "legs": [
                {"side": "short", "right": "put", "strike": 500, "delta": 0.25, "bid": 1.4, "ask": 1.6, "iv": 0.18},
                {"side": "long", "right": "put", "strike": 495, "delta": 0.12, "bid": 0.46, "ask": 0.54, "iv": 0.2},
            ],
            "thesis": "fixture",
            "confidence": 0.5,
        }
    )


def _bars_list(raw) -> list[dict]:
    if isinstance(raw, dict):
        raw = raw.get("bars", raw)
    if isinstance(raw, dict):
        # some shapes key bars by symbol: {"SPY": [...]}
        for v in raw.values():
            if isinstance(v, list):
                return v
        return []
    return raw if isinstance(raw, list) else []


def real_inputs(symbol: str) -> tuple[dict, dict]:
    """Live bars + live chain -> (regime kwargs, sliced candidates).

    Not covered by unit tests -- this is the I/O seam. If it raises, the caller
    prints a diagnostic and falls back to --fixture rather than crashing opaquely.
    """
    from strategy.chain import fetch_and_slice_chain
    from strategy.regime import compute_regime_inputs
    from tools.research_tools import get_stock_bars

    bars = _bars_list(asyncio.run(get_stock_bars(symbol, days=30)))
    sliced = fetch_and_slice_chain(symbol)
    return compute_regime_inputs(sliced, bars), sliced


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="SPY")
    p.add_argument(
        "--live",
        action="store_true",
        help="submit approved proposals to paper (requires EXPECTED_ACCOUNT_ID)",
    )
    p.add_argument(
        "--live-data",
        action="store_true",
        help="fetch live bars/chain for regime (still dry-run; no place_option_order)",
    )
    p.add_argument("--veto", action="store_true", help="force a universe veto fixture (exit 0)")
    p.add_argument("--atm-iv", type=float, default=0.22, help="only used with --fixture")
    p.add_argument("--rv", type=float, default=0.12, help="only used with --fixture")
    args = p.parse_args()
    create_all()

    if args.veto:
        out = dry_run(fixture_proposal("NVDA"), PortfolioView(nav=100_000), live=False)
        print("cycle veto", out.get("reason"))
        print(json.dumps({k: out[k] for k in out if k != "payload"}, indent=2))
        return 0

    if not args.live_data:
        cycle = run_cycle(
            args.symbol,
            atm_iv=args.atm_iv,
            rv_20=args.rv,
            rv_bar_count=20,
            breakout=False,
            chain_fn=lambda _s: {
                "short_candidates": [
                    {"symbol": "FIX", "right": "put", "strike": 500, "expiration": "2026-09-18",
                     "dte": 14, "delta": -0.25, "bid": 1.4, "ask": 1.6, "iv": 0.18}
                ],
                "long_candidates": [
                    {"symbol": "FIX", "right": "put", "strike": 495, "expiration": "2026-09-18",
                     "dte": 14, "delta": -0.12, "bid": 0.46, "ask": 0.54, "iv": 0.20}
                ],
            },
            propose_fn=lambda sym, _g: fixture_proposal(sym),
            critic_fn=lambda _p: None,  # keep this branch fully offline, not just the proposer
        )
    else:
        try:
            regime_kwargs, sliced = real_inputs(args.symbol)
        except Exception as exc:  # noqa: BLE001 - this is a CLI entry point, not library code
            print(f"live data fetch failed ({exc}); rerun with --fixture for an offline dry run", file=sys.stderr)
            return 3
        cycle = run_cycle(args.symbol, chain_fn=lambda _s: sliced, **regime_kwargs)

    print("cycle", cycle.verdict, cycle.reason)
    if cycle.critic is not None:
        print("critic:", cycle.critic.rebuttal)
    if cycle.proposal is None:
        return 0
    out = dry_run(cycle.proposal, PortfolioView(nav=100_000), live=args.live, critic=cycle.critic)
    print(json.dumps({k: out[k] for k in out if k != "payload"}, indent=2))
    if args.live and not out.get("ok") and out.get("reason") in {
        "ambiguous_timeout",
        "missing_broker_id",
        "broker_error",
        "unresolved_intent",
    }:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
