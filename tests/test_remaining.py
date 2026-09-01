from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from agents.critic import run_critic
from agents.schemas import CriticNote, TradeProposal
from execution.alpaca_py_fallback import build_mleg_request
from execution.expiry import should_sweep
from scheduler.cycle_loop import universe
from scheduler.market_hours import is_market_open
from storage.logger import log_event


def _proposal():
    return TradeProposal.model_validate(
        {
            "symbol": "SPY",
            "structure": "credit_spread",
            "expiration": "2026-09-18",
            "dte": 14,
            "legs": [
                {"side": "short", "right": "put", "strike": 500, "delta": 0.25, "bid": 1.4, "ask": 1.6, "iv": 0.18},
                {"side": "long", "right": "put", "strike": 495, "delta": 0.12, "bid": 0.46, "ask": 0.54, "iv": 0.2},
            ],
            "thesis": "t",
            "confidence": 0.4,
        }
    )


def test_critic_default():
    note = run_critic(_proposal())
    assert isinstance(note, CriticNote)
    assert note.invalidation


def test_logger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    log_event("veto", reason="universe", secret_key="nope")
    line = Path("logs/decisions.jsonl").read_text()
    assert "universe" in line
    assert "nope" not in line


def test_weekend_closed():
    sat = datetime(2026, 8, 29, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_market_open(sat) is False


def test_run_once_live_help_does_not_claim_refuse():
    from pathlib import Path

    src = Path("scripts/run_once.py").read_text()
    assert "refuse: live submit is not wired" not in src
    assert "EXPECTED_ACCOUNT_ID" in src


def test_cycle_universe():
    assert universe() == ["SPY", "QQQ", "IWM"]


def test_run_once_runs_agent_snapshot_and_reconcile(tmp_path):
    from agents.cycle import CycleResult
    from scheduler.cycle_loop import run_once
    from storage.db import create_all, recent_equity

    from risk.kill_switch import set_kill_switch

    set_kill_switch(False)
    db = tmp_path / "c.db"
    create_all(db)

    def cycle_fn(sym):
        return CycleResult(sym, None, "stand_down", "cheap_iv_rv")

    summary = run_once(
        path=db,
        equity_fn=lambda: 100_000.0,
        cycle_fn=cycle_fn,
        lookup_fn=lambda _c: None,
    )
    assert summary["candidates"] == ["SPY", "QQQ", "IWM"]
    assert summary["blocked"] is False
    assert len(summary["results"]) == 3
    assert all(r["verdict"] == "stand_down" for r in summary["results"])
    assert recent_equity(path=db)


def test_run_once_flattens_on_kill(tmp_path):
    import json

    from config.states import OrderStatus, StructureStatus
    from risk.kill_switch import set_kill_switch
    from scheduler.cycle_loop import run_once
    from storage.db import create_all
    from datetime import date

    from risk.engine import Leg, ProposalView
    from storage.ledger import get_structure, insert_order, insert_structure
    from strategy.structures import to_mleg_payload

    payload = to_mleg_payload(
        ProposalView(
            symbol="SPY",
            structure="credit_spread",
            dte=14,
            legs=[
                Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.18),
                Leg("long", "put", 495, 0.12, 0.46, 0.54, 0.20),
            ],
        ),
        client_order_id="entry",
        expiration=date(2026, 9, 18),
    )

    set_kill_switch(False)
    db = tmp_path / "k.db"
    create_all(db)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.FILLED.value,
        client_order_id="e-kill",
        qty=1,
        filled_qty=1,
        payload_json=json.dumps(payload),
        path=db,
    )
    seen = {"n": 0}

    def submit(_payload):
        seen["n"] += 1
        return {"id": "brk-flat"}

    set_kill_switch(True)
    try:
        summary = run_once(
            live=True,
            path=db,
            equity_fn=lambda: 100_000.0,
            lookup_fn=lambda _c: None,
            submit_fn=submit,
            skip_agent=True,
        )
    finally:
        set_kill_switch(False)
    assert summary["snapshot"] == "kill"
    assert seen["n"] == 1
    assert get_structure(sid, db)[2] == StructureStatus.CLOSING.value


def test_live_pass_blocks_without_account_equity(tmp_path, monkeypatch):
    from scheduler.cycle_loop import run_once
    from storage.db import create_all

    db = tmp_path / "noeq.db"
    create_all(db)
    monkeypatch.setattr("scheduler.cycle_loop.fetch_account_equity", lambda: None)
    summary = run_once(
        live=True,
        path=db,
        lookup_fn=lambda _c: None,
        skip_agent=True,
    )
    assert summary["blocked"] is True
    assert summary.get("reason") == "missing_account_equity"


def test_dry_run_pass_may_default_nav_without_account(tmp_path, monkeypatch):
    from scheduler.cycle_loop import resolve_equity
    from storage.db import create_all, insert_equity

    db = tmp_path / "dry.db"
    create_all(db)
    monkeypatch.setattr("scheduler.cycle_loop.fetch_account_equity", lambda: None)
    assert resolve_equity(live=False, equity_fn=None, path=db) == 100_000.0
    insert_equity(99_000.0, path=db)
    assert resolve_equity(live=True, equity_fn=None, path=db) is None
    assert resolve_equity(live=False, equity_fn=None, path=db) == 99_000.0


def test_kill_reports_flatten_incomplete(tmp_path, monkeypatch):
    from config.states import StructureStatus
    from risk.kill_switch import set_kill_switch
    from scheduler.loop import snapshot_and_maybe_flatten
    from storage.db import create_all
    from storage.ledger import insert_structure

    db = tmp_path / "inc.db"
    create_all(db)
    insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    set_kill_switch(True)
    try:
        why = snapshot_and_maybe_flatten(
            equity=100_000.0, sod=100_000.0, start=100_000.0, payloads={}, path=db
        )
    finally:
        set_kill_switch(False)
    assert why == "kill_flatten_incomplete"


def test_exit_outcome_reports_failed_submit(tmp_path):
    from config.states import StructureStatus
    from execution.close import close_structure
    from execution.exit_policy import evaluate_exits
    from storage.db import create_all
    from storage.ledger import insert_structure
    from tests.test_lifecycle import _payload

    db = tmp_path / "exfail.db"
    create_all(db)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)

    def close_fn(sid_, payload, **kw):
        return close_structure(sid_, payload, path=db, submit_fn=kw.get("submit_fn"))

    out = evaluate_exits(
        structure_id=sid,
        credit=1.0,
        mark=0.3,
        structure_status="OPEN",
        regime_stand_down=None,
        open_payload=_payload(),
        close_fn=close_fn,
        submit_fn=None,
    )
    assert out is not None
    assert out.trigger == "take_profit"
    assert out.submitted is False
    assert out.reason == "no_submit"


def test_run_once_exits_use_default_mark(tmp_path, monkeypatch):
    import json
    from datetime import date

    from config.states import OrderStatus, StructureStatus
    from risk.kill_switch import set_kill_switch
    from scheduler.cycle_loop import run_once
    from storage.db import create_all
    from storage.ledger import get_structure, insert_order, insert_structure
    from strategy.structures import to_mleg_payload
    from risk.engine import Leg, ProposalView

    set_kill_switch(False)
    db = tmp_path / "ex.db"
    create_all(db)
    payload = to_mleg_payload(
        ProposalView(
            symbol="SPY",
            structure="credit_spread",
            dte=14,
            legs=[
                Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.18),
                Leg("long", "put", 495, 0.12, 0.46, 0.54, 0.20),
            ],
        ),
        client_order_id="entry",
        expiration=date(2026, 9, 18),
    )
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.FILLED.value,
        client_order_id="e-mark",
        qty=1,
        filled_qty=1,
        payload_json=json.dumps(payload),
        path=db,
    )
    monkeypatch.setattr("scheduler.cycle_loop.mark_from_live_quotes", lambda _p: 0.3)
    monkeypatch.setattr("scheduler.cycle_loop._regime_stand_down", lambda _s: None)
    from agents.cycle import CycleResult

    summary = run_once(
        path=db,
        equity_fn=lambda: 100_000.0,
        cycle_fn=lambda sym: CycleResult(sym, None, "stand_down", "cheap_iv_rv"),
        lookup_fn=lambda _c: None,
        submit_fn=lambda _p: {"id": "brk-exit"},
    )
    assert any(e["reason"] == "take_profit" for e in summary["exits"])
    assert get_structure(sid, db)[2] == StructureStatus.CLOSING.value


def test_run_once_regime_exit_without_mark(tmp_path, monkeypatch):
    import json
    from datetime import date

    from agents.cycle import CycleResult
    from config.states import OrderStatus, StructureStatus
    from risk.engine import Leg, ProposalView
    from risk.kill_switch import set_kill_switch
    from scheduler.cycle_loop import run_once
    from storage.db import create_all
    from storage.ledger import get_structure, insert_order, insert_structure
    from strategy.structures import to_mleg_payload

    set_kill_switch(False)
    db = tmp_path / "reg.db"
    create_all(db)
    payload = to_mleg_payload(
        ProposalView(
            symbol="SPY",
            structure="credit_spread",
            dte=14,
            legs=[
                Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.18),
                Leg("long", "put", 495, 0.12, 0.46, 0.54, 0.20),
            ],
        ),
        client_order_id="entry",
        expiration=date(2026, 9, 18),
    )
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.FILLED.value,
        client_order_id="e-reg",
        qty=1,
        filled_qty=1,
        payload_json=json.dumps(payload),
        path=db,
    )
    monkeypatch.setattr("scheduler.cycle_loop.mark_from_live_quotes", lambda _p: None)
    summary = run_once(
        path=db,
        equity_fn=lambda: 100_000.0,
        cycle_fn=lambda sym: CycleResult(sym, None, "stand_down", "cheap_iv_rv"),
        lookup_fn=lambda _c: None,
        submit_fn=lambda _p: {"id": "brk-reg"},
    )
    assert any(e["reason"] == "regime" for e in summary["exits"])
    assert get_structure(sid, db)[2] == StructureStatus.CLOSING.value


def test_first_session_print_is_sod_not_first_ever(tmp_path):
    from datetime import datetime, timezone

    from scheduler.loop import snapshot_and_maybe_flatten
    from storage.db import connect, create_all

    db = tmp_path / "sod.db"
    create_all(db)
    con = connect(db)
    con.execute(
        "INSERT INTO equity_history(equity, ts) VALUES (?,?)",
        (110_000.0, "2026-08-30T20:00:00+00:00"),
    )
    con.commit()
    con.close()
    # 106k vs yesterday 110k is a 3.6% drop; vs today's first print it is 0.
    why = snapshot_and_maybe_flatten(
        equity=106_000.0, sod=110_000.0, start=110_000.0, payloads={}, path=db
    )
    assert why is None


def test_research_boards_render_without_st_table():
    from dashboard.components import article_board, blotter_board, scan_board, table_markdown

    scan_text = table_markdown([{"#": 1, "symbol": "NVDA"}])
    assert "NVDA" in scan_text
    assert callable(scan_board) and callable(article_board) and callable(blotter_board)


def test_dashboard_table_markdown_skips_json_blobs():
    from dashboard.components import table_markdown

    text = table_markdown(
        [
            {"id": 2, "symbol": "QQQ", "verdict": "approve_dry", "proposal_json": "{}"},
            {"id": 1, "symbol": "SPY", "verdict": "veto", "reason": "dte"},
        ]
    )
    assert "proposal_json" not in text
    assert "QQQ" in text and "SPY" in text
    assert text.splitlines()[0].startswith("|")


def test_net_mark_from_quotes():
    from execution.marks import net_mark

    payload = {
        "legs": [
            {"symbol": "SPY260918P00500000", "side": "sell"},
            {"symbol": "SPY260918P00495000", "side": "buy"},
        ]
    }
    quotes = {
        "SPY260918P00500000": (1.4, 1.6),
        "SPY260918P00495000": (0.46, 0.54),
    }
    assert abs(net_mark(payload, quotes) - 1.0) < 1e-9
    assert net_mark(payload, {"SPY260918P00500000": (1.4, 1.6)}) is None


def test_expiry_sweep():
    assert should_sweep(2) is True
    assert should_sweep(10) is False


def test_fallback_refuses_one_leg():
    import pytest

    with pytest.raises(ValueError):
        build_mleg_request({"legs": [{"symbol": "X", "ratio_qty": "1"}]})
