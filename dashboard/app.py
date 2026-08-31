from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from dashboard.components import activity, banner, curve, history, positions, tiles, transcript
from risk.kill_switch import is_killed, set_kill_switch
from storage.db import create_all, daily_pnl, recent_cycles, recent_equity
from storage.ledger import open_structures

st.set_page_config(page_title="ThetaGate", layout="wide")
banner()

replay = st.sidebar.toggle("Replay fixture", value=False)
fixture_path = Path("fixtures/replay_spy.json")

if replay and fixture_path.exists():
    data = json.loads(fixture_path.read_text())
    tiles(data["equity"], data["daily_pnl"], len(data["positions"]), data["killed"])
    curve([data["equity"] - 200, data["equity"] - 80, data["equity"]])
    positions(data["positions"])
    history(data["cycles"])
    transcript(data["cycles"])
    activity([f"{c['verdict']}: {c['reason']}" for c in data["cycles"]])
else:
    create_all()
    killed = is_killed()
    # Was hardcoded (100_000, 0, 0) regardless of real state -- equity/pnl now
    # come from equity_history (written by scheduler.loop.snapshot_and_maybe_flatten),
    # and open_n now uses the same `structs` count shown in the positions table
    # below instead of a second, disagreeing number.
    equity_rows = recent_equity()
    latest_equity = equity_rows[0]["equity"] if equity_rows else 100_000.0
    structs = [{"symbol": r[1], "status": r[2], "open_qty": r[3]} for r in open_structures()]
    tiles(latest_equity, daily_pnl(), len(structs), killed)
    if st.button("STOP"):
        set_kill_switch(True)
        st.rerun()
    if st.button("Resume"):
        set_kill_switch(False)
        st.rerun()
    positions(structs)
    cycles = recent_cycles(limit=10)
    history(cycles)
    transcript(cycles)
    activity([f"{c.get('symbol')} {c.get('verdict')} {c.get('reason')}" for c in cycles])
    curve([r["equity"] for r in reversed(equity_rows)] if equity_rows else [])
