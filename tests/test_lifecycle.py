from datetime import date
from pathlib import Path

import pytest

from config.states import OrderStatus, StructureStatus
from execution.cancel import cancel_entry_order
from execution.close import close_structure
from execution.exit_policy import evaluate_exits
from execution.flatten import flatten_all
from execution.reconcile import apply_broker_fill
from execution.recover import recover
from execution.transitions import IllegalTransition, step_order
from risk.engine import Leg, ProposalView
from scheduler.loop import snapshot_and_maybe_flatten
from storage.db import create_all, insert_intent
from storage.ledger import get_order, get_structure, insert_order, insert_structure
from strategy.structures import to_mleg_payload


def _db(tmp_path: Path) -> Path:
    p = tmp_path / "l.db"
    create_all(p)
    return p


def _ok_submit(_payload):
    return {"id": "brk-close"}


def _payload():
    pr = ProposalView(
        symbol="SPY",
        structure="credit_spread",
        dte=14,
        legs=[
            Leg("short", "put", 500, 0.25, 1.4, 1.6, 0.18),
            Leg("long", "put", 495, 0.12, 0.46, 0.54, 0.20),
        ],
    )
    return to_mleg_payload(pr, client_order_id="entry", expiration=date(2026, 9, 18))


def test_partial_then_cancel_leaves_structure_open(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e1",
        qty=2,
        path=db,
    )
    apply_broker_fill(oid, filled_qty=1, broker_status="partially_filled", path=db)
    o = get_order(oid, db)
    s = get_structure(sid, db)
    assert o[3] == OrderStatus.PARTIALLY_FILLED.value
    assert s[2] == StructureStatus.OPEN.value
    assert s[3] == 1
    cancel_entry_order(oid, path=db, lookup_fn=lambda _c: None)
    o = get_order(oid, db)
    s = get_structure(sid, db)
    # No broker id + not INTENT: ambiguous, must not invent CANCELED.
    assert o[3] == OrderStatus.NEEDS_REVIEW.value
    assert o[7] == 1
    assert s[2] == StructureStatus.OPEN.value
    assert s[2] != "CANCELED"


def test_close_rejected_reopens_structure(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    out = close_structure(sid, _payload(), path=db, submit_fn=_ok_submit)
    assert out["ok"] is True
    assert get_structure(sid, db)[2] == StructureStatus.CLOSING.value
    close_ord = get_order(out and 0 or 0, db)  # placeholder
    # find close order
    from storage.ledger import get_order_by_cid
    from execution.close import close_client_order_id

    row = get_order_by_cid(close_client_order_id(sid), db)
    apply_broker_fill(row[0], filled_qty=0, broker_status="rejected", path=db)
    assert get_structure(sid, db)[2] == StructureStatus.OPEN.value


def test_take_profit_then_fill_closes(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    calls = {"n": 0}

    def wrapped(sid_, payload, **kw):
        calls["n"] += 1
        return close_structure(sid_, payload, path=db, submit_fn=_ok_submit)

    reason = evaluate_exits(
        structure_id=sid,
        credit=1.0,
        mark=0.45,
        structure_status="OPEN",
        regime_stand_down=None,
        open_payload=_payload(),
        close_fn=wrapped,
    )
    assert reason is not None and reason.trigger == "take_profit"
    assert reason.submitted is True
    assert calls["n"] == 1
    assert get_structure(sid, db)[2] == StructureStatus.CLOSING.value
    from storage.ledger import latest_close_order

    row = latest_close_order(sid, db)
    apply_broker_fill(row[0], filled_qty=1, broker_status="filled", path=db)
    assert get_structure(sid, db)[2] == StructureStatus.CLOSED.value


def test_flatten_idempotent(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    payloads = {sid: _payload()}
    flatten_all("kill", payloads=payloads, path=db, submit_fn=_ok_submit)
    flatten_all("kill", payloads=payloads, path=db, submit_fn=_ok_submit)
    from storage.ledger import latest_close_order

    row = latest_close_order(sid, db)
    assert row is not None
    # still one close order
    import sqlite3

    n = sqlite3.connect(db).execute("SELECT count(*) FROM orders WHERE role='close'").fetchone()[0]
    assert n == 1


def test_refuse_one_leg_close(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    bad = {"qty": "1", "legs": [{"symbol": "X", "ratio_qty": "1", "side": "sell"}]}
    out = close_structure(sid, bad, path=db)
    assert getattr(out, "reason", None) == "refuse_non_atomic_close"
    assert get_structure(sid, db)[2] == StructureStatus.NEEDS_REVIEW.value


def test_illegal_order_transition():
    with pytest.raises(IllegalTransition):
        step_order(OrderStatus.FILLED, OrderStatus.WORKING)


def test_recover_canceled_not_closed(tmp_path):
    db = _db(tmp_path)
    insert_intent("c1", status=OrderStatus.NEEDS_REVIEW.value, path=db)
    assert recover("c1", path=db) == "wait_reconcile"


def test_snapshot_writes_equity(tmp_path):
    db = _db(tmp_path)
    snapshot_and_maybe_flatten(equity=100_000, sod=100_000, start=100_000, payloads={}, path=db)
    import sqlite3

    n = sqlite3.connect(db).execute("SELECT count(*) FROM equity_history").fetchone()[0]
    assert n == 1


def test_flatten_falls_back_to_stored_entry_payload(tmp_path, monkeypatch):
    """Regression: flatten_all used to silently skip a structure whenever the
    caller's payloads dict didn't have an entry for it, even if the entry
    payload was already sitting in the DB."""
    monkeypatch.chdir(tmp_path)
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, path=db)
    import json

    insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e1",
        broker_order_id="brk-e1",
        qty=1,
        filled_qty=1,
        payload_json=json.dumps(_payload()),
        path=db,
    )
    n = flatten_all(
        "kill",
        payloads={},
        path=db,
        submit_fn=_ok_submit,
        lookup_fn=lambda _c: None,
        cancel_fn=lambda _i: {"status": "canceled"},
    )
    assert n.submitted == 1
    assert n.complete is True
    from storage.ledger import get_order_by_cid
    from execution.close import close_client_order_id

    assert get_order_by_cid(close_client_order_id(sid), db) is not None


def test_flatten_logs_and_counts_when_nothing_can_be_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = _db(tmp_path)
    insert_structure("SPY", status=StructureStatus.OPEN.value, path=db)  # no entry order at all
    n = flatten_all("kill", payloads={}, path=db, submit_fn=_ok_submit)
    assert n.submitted == 0
    assert n.skipped == 1
    assert n.complete is False
    log = Path("logs/decisions.jsonl").read_text()
    assert "flatten_skip_no_payload" in log
    assert "flatten_incomplete" in log


def test_close_without_submit_does_not_claim_closing(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    from execution.close import FailClosed

    out = close_structure(sid, _payload(), path=db)
    assert isinstance(out, FailClosed)
    assert out.reason == "no_submit"
    assert get_structure(sid, db)[2] == StructureStatus.OPEN.value


def test_flatten_does_not_count_fail_closed(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    n = flatten_all("kill", payloads={sid: _payload()}, path=db)  # no submit_fn
    assert n.submitted == 0
    assert n.failed == 1
    assert n.complete is False
    assert get_structure(sid, db)[2] == StructureStatus.OPEN.value


def test_cancel_calls_broker_when_broker_id_present(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-cancel",
        broker_order_id="brk-cancel",
        qty=1,
        path=db,
    )
    seen = {}

    def fake_cancel(order_id):
        seen["id"] = order_id
        return {"status": "canceled"}

    cancel_entry_order(oid, path=db, cancel_fn=fake_cancel)
    assert seen["id"] == "brk-cancel"
    assert get_order(oid, db)[3] == OrderStatus.CANCELED.value


def test_cancel_unconfirmed_response_is_requested_not_canceled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-pend",
        broker_order_id="brk-pend",
        qty=1,
        path=db,
    )
    out = cancel_entry_order(oid, path=db, cancel_fn=lambda _i: {"status": "accepted"})
    assert out == OrderStatus.CANCEL_REQUESTED.value
    assert get_order(oid, db)[3] == OrderStatus.CANCEL_REQUESTED.value
    log = Path("logs/decisions.jsonl").read_text()
    assert "cancel_requested" in log


def test_cancel_error_envelope_is_not_canceled(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-err",
        broker_order_id="brk-err",
        qty=1,
        path=db,
    )
    cancel_entry_order(oid, path=db, cancel_fn=lambda _i: {"error": "mcp failed"})
    assert get_order(oid, db)[3] == OrderStatus.CANCEL_REQUESTED.value


def test_cancel_exception_is_not_canceled(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-boom",
        broker_order_id="brk-boom",
        qty=1,
        path=db,
    )

    def boom(_i):
        raise TimeoutError("cancel timed out")

    cancel_entry_order(oid, path=db, cancel_fn=boom)
    assert get_order(oid, db)[3] == OrderStatus.CANCEL_REQUESTED.value


def test_reconcile_confirms_cancel_requested(tmp_path):
    from execution.reconcile import reconcile_working

    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.CANCEL_REQUESTED.value,
        client_order_id="e-rec",
        broker_order_id="brk-rec",
        qty=1,
        path=db,
    )
    n = reconcile_working(path=db, lookup_fn=lambda _c: {"status": "canceled", "filled_qty": 0})
    assert n == 1
    assert get_order(oid, db)[3] == OrderStatus.CANCELED.value


def test_reconcile_lookup_failure_marks_needs_review(tmp_path, monkeypatch):
    from execution.reconcile import reconcile_working

    monkeypatch.chdir(tmp_path)
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-lookup",
        qty=1,
        path=db,
    )

    def boom(_c):
        raise RuntimeError("mcp down")

    n = reconcile_working(path=db, lookup_fn=boom)
    assert n == 0
    assert get_order(oid, db)[3] == OrderStatus.NEEDS_REVIEW.value
    assert "reconcile_needs_review" in Path("logs/decisions.jsonl").read_text()


def test_reconcile_bad_shape_marks_needs_review(tmp_path, monkeypatch):
    from execution.reconcile import reconcile_working

    monkeypatch.chdir(tmp_path)
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-shape",
        qty=1,
        path=db,
    )
    reconcile_working(path=db, lookup_fn=lambda _c: "not-a-dict")
    assert get_order(oid, db)[3] == OrderStatus.NEEDS_REVIEW.value


def test_close_intent_persists_payload_before_submit(tmp_path):
    from execution.close import close_client_order_id
    from storage.db import get_intent_row

    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    close_structure(sid, _payload(), path=db, submit_fn=_ok_submit)
    row = get_intent_row(close_client_order_id(sid), db)
    assert row is not None
    assert row["symbol"] == "SPY"
    assert row["structure_id"] == sid
    assert row["payload_json"]
    assert "legs" in row["payload_json"]


def test_recover_startup_restores_close_onto_existing_structure(tmp_path):
    import json

    from execution.close import close_client_order_id
    from execution.recover import recover_startup
    from storage.db import insert_intent
    from storage.ledger import get_order_by_cid

    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    cid = close_client_order_id(sid)
    insert_intent(
        cid,
        status=OrderStatus.SUBMITTING.value,
        symbol="SPY",
        payload_json=json.dumps(_payload()),
        structure_id=sid,
        path=db,
    )
    assert recover_startup(path=db, lookup_fn=lambda _c: {"id": "brk-close-restored"}) == "ok"
    row = get_order_by_cid(cid, db)
    assert row is not None
    assert row[1] == sid
    assert row[2] == "close"
    assert row[5] == "brk-close-restored"
    assert get_structure(sid, db)[2] == StructureStatus.CLOSING.value


def test_recover_uses_payload_qty(tmp_path):
    import json

    from execution.recover import recover_startup
    from storage.db import insert_intent
    from storage.ledger import get_order_by_cid

    db = _db(tmp_path)
    insert_intent(
        "tg-qty",
        status=OrderStatus.SUBMITTING.value,
        symbol="SPY",
        payload_json=json.dumps({"qty": "3", "order_class": "mleg", "legs": [{}, {}]}),
        path=db,
    )
    assert recover_startup(path=db, lookup_fn=lambda _c: {"id": "brk-qty"}) == "ok"
    row = get_order_by_cid("tg-qty", db)
    assert row[6] == 3.0


def test_recover_startup_restores_missing_order_and_clears_block(tmp_path):
    from execution.recover import recover_startup
    from storage.db import insert_intent

    db = _db(tmp_path)
    insert_intent(
        "tg-restore",
        status=OrderStatus.SUBMITTING.value,
        symbol="SPY",
        payload_json='{"order_class":"mleg","legs":[{},{}]}',
        path=db,
    )
    assert recover_startup(path=db, lookup_fn=lambda _c: None) == "block_startup"
    assert recover_startup(path=db, lookup_fn=lambda _c: {"id": "brk-restored"}) == "ok"
    from storage.ledger import get_order_by_cid

    row = get_order_by_cid("tg-restore", db)
    assert row is not None
    assert row[5] == "brk-restored"


def test_canceled_zero_fill_close_reopens(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    out = close_structure(sid, _payload(), path=db, submit_fn=_ok_submit)
    from execution.close import close_client_order_id
    from storage.ledger import get_order_by_cid

    row = get_order_by_cid(close_client_order_id(sid), db)
    apply_broker_fill(row[0], filled_qty=0, broker_status="canceled", path=db)
    assert get_structure(sid, db)[2] == StructureStatus.OPEN.value


def test_expired_partial_close_needs_review(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    close_structure(sid, _payload(), path=db, submit_fn=_ok_submit)
    from execution.close import close_client_order_id
    from storage.ledger import get_order_by_cid

    row = get_order_by_cid(close_client_order_id(sid), db)
    apply_broker_fill(row[0], filled_qty=1, broker_status="expired", path=db)
    assert get_structure(sid, db)[2] == StructureStatus.NEEDS_REVIEW.value


def test_canceled_zero_fill_entry_voids_structure(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-void",
        broker_order_id="brk-void",
        qty=1,
        path=db,
    )
    apply_broker_fill(oid, filled_qty=0, broker_status="canceled", path=db)
    assert get_structure(sid, db)[2] == StructureStatus.VOID.value


def test_cancel_submitting_without_broker_id_is_ambiguous(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.SUBMITTING.value,
        client_order_id="e-amb",
        qty=1,
        path=db,
    )
    out = cancel_entry_order(oid, path=db, lookup_fn=lambda _c: None)
    assert out == OrderStatus.NEEDS_REVIEW.value
    assert get_order(oid, db)[3] == OrderStatus.NEEDS_REVIEW.value
    assert get_structure(sid, db)[2] == StructureStatus.PENDING_ENTRY.value


def test_cancel_intent_without_broker_id_is_local(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.INTENT.value,
        client_order_id="e-intent",
        qty=1,
        path=db,
    )
    out = cancel_entry_order(oid, path=db)
    assert out == OrderStatus.CANCELED.value
    assert get_structure(sid, db)[2] == StructureStatus.VOID.value


def test_active_structures_include_closing_and_needs_review(tmp_path):
    from storage.ledger import active_structures, pending_entries

    db = _db(tmp_path)
    insert_structure("SPY", status=StructureStatus.OPEN.value, path=db)
    insert_structure("QQQ", status=StructureStatus.CLOSING.value, path=db)
    insert_structure("IWM", status=StructureStatus.NEEDS_REVIEW.value, path=db)
    insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    insert_structure("SPY", status=StructureStatus.VOID.value, path=db)
    insert_structure("SPY", status=StructureStatus.CLOSED.value, path=db)
    active = {r[2] for r in active_structures(db)}
    assert active == {
        StructureStatus.OPEN.value,
        StructureStatus.CLOSING.value,
        StructureStatus.NEEDS_REVIEW.value,
    }
    assert len(pending_entries(db)) == 1


def test_halt_cancels_pending_entry_before_flatten(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-pend-halt",
        broker_order_id="brk-pend-halt",
        qty=1,
        path=db,
    )
    seen = {}

    def fake_cancel(order_id):
        seen["id"] = order_id
        return {"status": "canceled"}

    n = flatten_all(
        "kill",
        payloads={},
        path=db,
        submit_fn=_ok_submit,
        cancel_fn=fake_cancel,
        lookup_fn=lambda _c: None,
    )
    assert seen["id"] == "brk-pend-halt"
    assert get_order(oid, db)[3] == OrderStatus.CANCELED.value
    assert get_structure(sid, db)[2] == StructureStatus.VOID.value
    assert n.canceled == 1
    assert n.cancel_unresolved == 0
    assert n.remaining == 0
    assert n.complete is True


def test_halt_incomplete_when_pending_cancel_unconfirmed(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-pend-unc",
        broker_order_id="brk-pend-unc",
        qty=1,
        path=db,
    )
    n = flatten_all(
        "kill",
        payloads={},
        path=db,
        submit_fn=_ok_submit,
        cancel_fn=lambda _i: {"status": "accepted"},
        lookup_fn=lambda _c: None,
    )
    assert n.complete is False
    assert n.cancel_unresolved == 1
    assert get_structure(sid, db)[2] == StructureStatus.PENDING_ENTRY.value


def test_halt_cancels_partial_then_flattens_fill(tmp_path):
    import json

    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    entry = _payload()
    entry["qty"] = "2"
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-part-halt",
        broker_order_id="brk-part-halt",
        qty=2,
        payload_json=json.dumps(entry),
        path=db,
    )
    apply_broker_fill(oid, filled_qty=1, broker_status="partially_filled", path=db)
    assert get_structure(sid, db)[2] == StructureStatus.OPEN.value
    assert get_structure(sid, db)[3] == 1
    seen = {}

    def submit(payload):
        seen["payload"] = payload
        return {"id": "brk-close"}

    n = flatten_all(
        "kill",
        payloads={},
        path=db,
        submit_fn=submit,
        cancel_fn=lambda _i: {"status": "canceled"},
        lookup_fn=lambda _c: None,
    )
    assert get_order(oid, db)[3] == OrderStatus.CANCELED.value
    assert get_structure(sid, db)[2] == StructureStatus.CLOSING.value
    assert n.canceled == 1
    assert n.submitted == 1
    assert n.complete is True
    assert seen["payload"]["qty"] == "1"


def test_halt_needs_review_entry_confirmed_cancel_voids(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.NEEDS_REVIEW.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.NEEDS_REVIEW.value,
        client_order_id="e-nr-halt",
        broker_order_id="brk-nr-halt",
        qty=1,
        path=db,
    )
    n = flatten_all(
        "kill",
        payloads={},
        path=db,
        submit_fn=_ok_submit,
        cancel_fn=lambda _i: {"status": "canceled"},
        lookup_fn=lambda _c: None,
    )
    assert get_order(oid, db)[3] == OrderStatus.CANCELED.value
    assert get_structure(sid, db)[2] == StructureStatus.VOID.value
    assert n.complete is True


def test_halt_needs_review_unconfirmed_cancel_stays_review(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.NEEDS_REVIEW.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.NEEDS_REVIEW.value,
        client_order_id="e-nr-unc",
        broker_order_id="brk-nr-unc",
        qty=1,
        path=db,
    )
    n = flatten_all(
        "kill",
        payloads={},
        path=db,
        submit_fn=_ok_submit,
        cancel_fn=lambda _i: {"status": "accepted"},
        lookup_fn=lambda _c: None,
    )
    assert get_order(oid, db)[3] == OrderStatus.NEEDS_REVIEW.value
    assert get_structure(sid, db)[2] == StructureStatus.NEEDS_REVIEW.value
    assert n.complete is False


def test_flatten_attempts_needs_review_exposure(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.NEEDS_REVIEW.value, open_qty=1, path=db)
    n = flatten_all("kill", payloads={sid: _payload()}, path=db, submit_fn=_ok_submit)
    assert n.submitted == 1
    assert get_structure(sid, db)[2] == StructureStatus.CLOSING.value


def test_stale_entry_sweep_cancels_old_working(tmp_path):
    from datetime import datetime, timedelta, timezone

    from execution.cancel import cancel_stale_entries
    from storage.db import connect

    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-stale",
        broker_order_id="brk-stale",
        qty=1,
        path=db,
    )
    old = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    con = connect(db)
    con.execute("UPDATE orders SET created_ts=? WHERE id=?", (old, oid))
    con.commit()
    con.close()
    seen = {}

    def fake_cancel(order_id):
        seen["id"] = order_id
        return {"status": "canceled"}

    out = cancel_stale_entries(path=db, timeout_minutes=30, cancel_fn=fake_cancel)
    assert oid in out
    assert seen["id"] == "brk-stale"
    assert get_order(oid, db)[3] == OrderStatus.CANCELED.value
    assert get_structure(sid, db)[2] == StructureStatus.VOID.value


def test_rejected_close_can_be_retried_with_new_id(tmp_path):
    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.OPEN.value, open_qty=1, path=db)
    first = close_structure(sid, _payload(), path=db, submit_fn=_ok_submit)
    from storage.ledger import latest_close_order

    row = latest_close_order(sid, db)
    apply_broker_fill(row[0], filled_qty=0, broker_status="rejected", path=db)
    assert get_structure(sid, db)[2] == StructureStatus.OPEN.value
    second = close_structure(sid, _payload(), path=db, submit_fn=_ok_submit)
    assert second["submitted"] is True
    assert second["client_order_id"] != first["client_order_id"]
    import sqlite3

    n = sqlite3.connect(db).execute("SELECT count(*) FROM orders WHERE role='close'").fetchone()[0]
    assert n == 2


def test_ambiguous_close_without_broker_id_cannot_resubmit(tmp_path):
    from execution.close import FailClosed, close_client_order_id
    from storage.db import insert_intent

    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.NEEDS_REVIEW.value, open_qty=1, path=db)
    insert_intent(
        close_client_order_id(sid, 1),
        status=OrderStatus.NEEDS_REVIEW.value,
        symbol="SPY",
        payload_json="{}",
        structure_id=sid,
        path=db,
    )
    out = close_structure(sid, _payload(), path=db, submit_fn=_ok_submit)
    assert isinstance(out, FailClosed)
    assert out.reason == "unresolved_close"


def test_stale_null_created_ts_is_swept(tmp_path):
    from execution.cancel import cancel_stale_entries
    from storage.db import connect

    db = _db(tmp_path)
    sid = insert_structure("SPY", status=StructureStatus.PENDING_ENTRY.value, path=db)
    oid = insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id="e-nullts",
        broker_order_id="brk-nullts",
        qty=1,
        path=db,
    )
    con = connect(db)
    con.execute("UPDATE orders SET created_ts=NULL WHERE id=?", (oid,))
    con.commit()
    con.close()
    out = cancel_stale_entries(
        path=db, timeout_minutes=30, cancel_fn=lambda _i: {"status": "canceled"}
    )
    assert oid in out
    assert get_order(oid, db)[3] == OrderStatus.CANCELED.value


def test_scheduler_does_not_live_in_flatten():
    import ast

    tree = ast.parse(Path("execution/flatten.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(not a.name.startswith("scheduler") for a in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("scheduler")
