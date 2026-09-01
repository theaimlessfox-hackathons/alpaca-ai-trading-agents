"""015 — cancel stale entry orders. Does not set StructureStatus to CLOSED."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.states import OrderStatus
from execution.reconcile import apply_broker_fill
from execution.transitions import step_order
from storage.db import DEFAULT_PATH, insert_intent
from storage.ledger import get_order, get_structure, update_order


def _cancel_outcome(result) -> str:
    """Only a clear canceled status is confirmation. Everything else is unconfirmed."""
    if isinstance(result, dict):
        if result.get("error") or result.get("isError") is True:
            return "unconfirmed"
        data = result.get("data") if isinstance(result.get("data"), dict) else result
        status = str(data.get("status") or data.get("order_status") or "").lower()
        if status in {"canceled", "cancelled"}:
            return "canceled"
        if status in {"pending_cancel", "pending_cancellation"}:
            return "pending"
    return "unconfirmed"


def _mark_cancel_requested(order_id: int, cid: str | None, cur: OrderStatus, *, path: Path) -> str:
    from storage.logger import log_event

    # An unconfirmed cancel of an already-ambiguous order stays NEEDS_REVIEW.
    if cur is OrderStatus.NEEDS_REVIEW:
        log_event("cancel_unconfirmed_stays_review", order_id=order_id, client_order_id=cid)
        return OrderStatus.NEEDS_REVIEW.value
    nxt = step_order(cur, OrderStatus.CANCEL_REQUESTED)
    update_order(order_id, status=nxt.value, path=path)
    if cid:
        insert_intent(cid, status=OrderStatus.CANCEL_REQUESTED.value, path=path)
    log_event("cancel_requested", order_id=order_id, client_order_id=cid)
    return nxt.value


def _lookup_broker_id(cid: str | None, lookup_fn: Callable[[str], object] | None) -> str | None:
    if not cid:
        return None
    try:
        if lookup_fn is not None:
            found = lookup_fn(cid)
        else:
            from tools.account_tools import get_order_by_client_id_sync

            found = get_order_by_client_id_sync(cid)
    except Exception:  # noqa: BLE001 - lookup failure leaves the order unresolved
        return None
    if not isinstance(found, dict):
        return None
    from execution.executor import _extract_broker_order_id

    return _extract_broker_order_id(found)


def _cancel_at_broker(
    order_id: int,
    *,
    sid: int,
    cid: str | None,
    cur: OrderStatus,
    broker_id: str,
    filled: float,
    path: Path,
    cancel_fn: Callable[[str], object] | None,
) -> str:
    fn = cancel_fn
    if fn is None:
        from execution.broker import cancel_order_sync

        fn = cancel_order_sync
    try:
        result = fn(str(broker_id))
    except Exception:  # noqa: BLE001 - request may have reached Alpaca; do not invent CANCELED
        return _mark_cancel_requested(order_id, cid, cur, path=path)
    outcome = _cancel_outcome(result)
    if outcome == "canceled":
        apply_broker_fill(order_id, filled_qty=filled, broker_status="canceled", path=path)
        struct = get_structure(sid, path)
        if struct and filled > 0:
            assert struct[2] != "CLOSED"
            assert struct[2] != "CANCELED"
        return OrderStatus.CANCELED.value
    return _mark_cancel_requested(order_id, cid, cur, path=path)


def cancel_entry_order(
    order_id: int,
    *,
    path: Path = DEFAULT_PATH,
    cancel_fn: Callable[[str], object] | None = None,
    lookup_fn: Callable[[str], object] | None = None,
) -> str:
    order = get_order(order_id, path)
    if not order:
        raise KeyError(order_id)
    _oid, sid, role, st, cid, broker_id, qty, filled = order
    if role != "entry":
        raise ValueError("only entry orders")
    if st in {OrderStatus.FILLED.value, OrderStatus.CANCELED.value, OrderStatus.EXPIRED.value}:
        return st
    cur = OrderStatus(st)
    if not broker_id:
        # Only a pre-submit INTENT is known not to have reached Alpaca.
        # SUBMITTING / WORKING / NEEDS_REVIEW without an id may already be live.
        if cur is OrderStatus.INTENT:
            apply_broker_fill(order_id, filled_qty=filled, broker_status="canceled", path=path)
            return OrderStatus.CANCELED.value
        resolved = _lookup_broker_id(cid, lookup_fn)
        if resolved:
            return _cancel_at_broker(
                order_id,
                sid=sid,
                cid=cid,
                cur=cur,
                broker_id=resolved,
                filled=filled,
                path=path,
                cancel_fn=cancel_fn,
            )
        insert_intent(cid or f"missing-{order_id}", status=OrderStatus.NEEDS_REVIEW.value, path=path)
        update_order(order_id, status=OrderStatus.NEEDS_REVIEW.value, path=path)
        from storage.logger import log_event

        log_event("cancel_ambiguous_no_broker_id", order_id=order_id, client_order_id=cid, status=st)
        return OrderStatus.NEEDS_REVIEW.value
    return _cancel_at_broker(
        order_id,
        sid=sid,
        cid=cid,
        cur=cur,
        broker_id=str(broker_id),
        filled=filled,
        path=path,
        cancel_fn=cancel_fn,
    )


_NONTERMINAL_ENTRY = {
    OrderStatus.INTENT.value,
    OrderStatus.SUBMITTING.value,
    OrderStatus.WORKING.value,
    OrderStatus.PARTIALLY_FILLED.value,
    OrderStatus.CANCEL_REQUESTED.value,
    OrderStatus.NEEDS_REVIEW.value,
}


def cancel_nonterminal_entries(
    *,
    path: Path = DEFAULT_PATH,
    cancel_fn: Callable[[str], object] | None = None,
    lookup_fn: Callable[[str], object] | None = None,
) -> tuple[list[int], list[int]]:
    """Cancel every entry that can still fill. Returns (resolved, unresolved)."""
    from storage.ledger import list_orders

    resolved: list[int] = []
    unresolved: list[int] = []
    for row in list_orders(path, role="entry"):
        oid, _sid, _role, st, _cid, _br, _qty, _fq = row
        if st not in _NONTERMINAL_ENTRY:
            continue
        out = cancel_entry_order(oid, path=path, cancel_fn=cancel_fn, lookup_fn=lookup_fn)
        if out in {
            OrderStatus.CANCELED.value,
            OrderStatus.EXPIRED.value,
            OrderStatus.REJECTED.value,
        }:
            resolved.append(oid)
        else:
            unresolved.append(oid)
    return resolved, unresolved


def cancel_stale_entries(
    *,
    path: Path = DEFAULT_PATH,
    now: datetime | None = None,
    timeout_minutes: int | None = None,
    cancel_fn: Callable[[str], object] | None = None,
    lookup_fn: Callable[[str], object] | None = None,
) -> list[int]:
    """Cancel unfilled/working entries older than entry_timeout_minutes."""
    from config.settings import get_settings
    from storage.ledger import list_entry_orders_with_ts

    minutes = timeout_minutes if timeout_minutes is not None else get_settings().entry_timeout_minutes
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=minutes)
    statuses = (
        OrderStatus.WORKING.value,
        OrderStatus.SUBMITTING.value,
        OrderStatus.PARTIALLY_FILLED.value,
    )
    canceled: list[int] = []
    for oid, _sid, _st, _cid, _br, created_ts in list_entry_orders_with_ts(path, statuses=statuses):
        if not created_ts:
            # Migrated pre-timestamp rows: age is unknown, treat as stale.
            cancel_entry_order(oid, path=path, cancel_fn=cancel_fn, lookup_fn=lookup_fn)
            canceled.append(oid)
            continue
        try:
            ts = datetime.fromisoformat(str(created_ts))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts > cutoff:
            continue
        cancel_entry_order(oid, path=path, cancel_fn=cancel_fn, lookup_fn=lookup_fn)
        canceled.append(oid)
    return canceled
