"""Apply broker order status. Never copies CANCELED onto the structure."""

from __future__ import annotations

from pathlib import Path

from config.states import OrderStatus, StructureStatus
from execution.transitions import step_order, step_structure
from storage.db import DEFAULT_PATH
from storage.ledger import get_order, get_structure, update_order, update_structure


def apply_broker_fill(
    order_id: int,
    *,
    filled_qty: float,
    broker_status: str,
    path: Path = DEFAULT_PATH,
) -> None:
    order = get_order(order_id, path)
    if not order:
        raise KeyError(order_id)
    _oid, sid, role, st, _cid, _br, qty, _fq = order
    cur = OrderStatus(st)
    b = broker_status.lower()
    if b in {"new", "accepted", "pending_new"}:
        nxt = step_order(cur, OrderStatus.WORKING)
    elif b in {"partially_filled", "partial"}:
        nxt = step_order(cur, OrderStatus.PARTIALLY_FILLED)
    elif b == "filled":
        nxt = step_order(cur, OrderStatus.FILLED)
    elif b in {"pending_cancel", "pending_cancellation"}:
        nxt = step_order(cur, OrderStatus.CANCEL_REQUESTED)
    elif b in {"canceled", "cancelled"}:
        nxt = step_order(cur, OrderStatus.CANCELED)
    elif b == "rejected":
        nxt = step_order(cur, OrderStatus.REJECTED)
    elif b == "expired":
        nxt = step_order(cur, OrderStatus.EXPIRED)
    else:
        nxt = step_order(cur, OrderStatus.NEEDS_REVIEW)
    update_order(order_id, status=nxt.value, filled_qty=filled_qty, path=path)

    struct = get_structure(sid, path)
    if not struct:
        return
    sst = StructureStatus(struct[2])
    if role == "entry":
        if filled_qty > 0:
            if sst is StructureStatus.PENDING_ENTRY:
                sst = step_structure(sst, StructureStatus.OPEN)
            update_structure(sid, status=sst.value, open_qty=filled_qty, path=path)
        elif nxt in {OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED}:
            if sst is StructureStatus.PENDING_ENTRY:
                update_structure(sid, status=step_structure(sst, StructureStatus.VOID).value, open_qty=0, path=path)
    elif role == "close":
        if nxt is OrderStatus.FILLED:
            update_structure(sid, status=step_structure(sst, StructureStatus.CLOSED).value, open_qty=0, path=path)
        elif nxt is OrderStatus.REJECTED and sst is StructureStatus.CLOSING:
            update_structure(sid, status=step_structure(sst, StructureStatus.OPEN).value, path=path)
        elif nxt in {OrderStatus.CANCELED, OrderStatus.EXPIRED}:
            if filled_qty > 0:
                update_structure(sid, status=StructureStatus.NEEDS_REVIEW.value, path=path)
            elif sst is StructureStatus.CLOSING:
                update_structure(sid, status=step_structure(sst, StructureStatus.OPEN).value, path=path)
        elif nxt is OrderStatus.PARTIALLY_FILLED:
            update_structure(sid, status=StructureStatus.NEEDS_REVIEW.value, path=path)


def _mark_reconcile_review(oid: int, cid: str | None, reason: str, *, path: Path, **extra) -> None:
    from storage.db import insert_intent
    from storage.ledger import update_order
    from storage.logger import log_event

    update_order(oid, status=OrderStatus.NEEDS_REVIEW.value, path=path)
    if cid:
        insert_intent(cid, status=OrderStatus.NEEDS_REVIEW.value, path=path)
    log_event("reconcile_needs_review", order_id=oid, client_order_id=cid, reason=reason, **extra)


def reconcile_working(*, path: Path = DEFAULT_PATH, lookup_fn=None) -> int:
    """Apply broker status for in-flight orders. Failures are audited and
    marked NEEDS_REVIEW — they must not sit in WORKING forever."""
    from storage.ledger import list_orders

    statuses = (
        OrderStatus.SUBMITTING.value,
        OrderStatus.WORKING.value,
        OrderStatus.PARTIALLY_FILLED.value,
        OrderStatus.CANCEL_REQUESTED.value,
    )
    n = 0
    for row in list_orders(path, statuses=statuses):
        oid, _sid, _role, _st, cid, _br, _qty, filled_qty = row
        if not cid:
            _mark_reconcile_review(oid, None, "missing_client_order_id", path=path)
            continue
        found = None
        try:
            if lookup_fn is not None:
                found = lookup_fn(cid)
            else:
                from tools.account_tools import get_order_by_client_id_sync

                found = get_order_by_client_id_sync(cid)
        except Exception as exc:  # noqa: BLE001 - lookup failure is an unresolved state
            _mark_reconcile_review(oid, cid, "lookup_failed", path=path, detail=type(exc).__name__)
            continue
        if not isinstance(found, dict):
            _mark_reconcile_review(oid, cid, "bad_shape", path=path, detail=type(found).__name__)
            continue
        status = str(found.get("status") or found.get("order_status") or "")
        if not status:
            _mark_reconcile_review(oid, cid, "missing_status", path=path)
            continue
        filled = found.get("filled_qty")
        if filled is None:
            filled = found.get("filled_quantity")
        if filled is None:
            filled = filled_qty or 0
        try:
            apply_broker_fill(oid, filled_qty=float(filled), broker_status=status, path=path)
            n += 1
        except Exception as exc:  # noqa: BLE001 - illegal transition / parse error
            _mark_reconcile_review(oid, cid, "apply_failed", path=path, detail=type(exc).__name__)
            continue
    return n
