"""016 — atomic multi-leg close or fail closed. Idempotent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from config.states import OrderStatus, StructureStatus
from execution.transitions import step_structure
from storage.db import DEFAULT_PATH, insert_intent, list_intents
from storage.ledger import get_structure, insert_order, list_orders, update_structure
from strategy.structures import close_mleg_payload

_UNRESOLVED_CLOSE = {
    OrderStatus.INTENT.value,
    OrderStatus.SUBMITTING.value,
    OrderStatus.WORKING.value,
    OrderStatus.PARTIALLY_FILLED.value,
    OrderStatus.CANCEL_REQUESTED.value,
    OrderStatus.NEEDS_REVIEW.value,
}

_LOCKS: dict[int, Lock] = {}
_META = Lock()


def _lock(sid: int) -> Lock:
    with _META:
        return _LOCKS.setdefault(sid, Lock())


@dataclass
class FailClosed:
    reason: str


def close_client_order_id(structure_id: int, attempt: int = 1) -> str:
    return f"tg-close-{structure_id}-{attempt}"


def is_close_cid(cid: str, structure_id: int) -> bool:
    return cid == f"tg-close-{structure_id}" or cid.startswith(f"tg-close-{structure_id}-")


def close_attempt_number(cid: str, structure_id: int) -> int:
    prefix = f"tg-close-{structure_id}-"
    if cid.startswith(prefix):
        try:
            return int(cid[len(prefix) :])
        except ValueError:
            return 1
    if cid == f"tg-close-{structure_id}":
        return 1
    return 0


def next_close_client_order_id(structure_id: int, path: Path = DEFAULT_PATH) -> str:
    n = 1
    for row in list_orders(path, role="close", structure_id=structure_id):
        cid = row[4]
        if cid:
            n = max(n, close_attempt_number(cid, structure_id) + 1)
    for cid, _bid, _st, _sym, _payload in list_intents(path):
        if is_close_cid(cid, structure_id):
            n = max(n, close_attempt_number(cid, structure_id) + 1)
    return close_client_order_id(structure_id, n)


_IN_FLIGHT = {
    OrderStatus.SUBMITTING.value,
    OrderStatus.WORKING.value,
    OrderStatus.PARTIALLY_FILLED.value,
    OrderStatus.CANCEL_REQUESTED.value,
}
_TERMINAL_CLOSE = {
    OrderStatus.CANCELED.value,
    OrderStatus.EXPIRED.value,
    OrderStatus.REJECTED.value,
    OrderStatus.FILLED.value,
}


def _unresolved_close(structure_id: int, path: Path) -> tuple[str, object] | None:
    """In-flight closes block as existing; ambiguous (no terminal order) as FailClosed."""
    orders = list_orders(path, role="close", structure_id=structure_id)
    for row in orders:
        if row[3] in _IN_FLIGHT:
            return ("in_flight", row)
    terminal_cids = {row[4] for row in orders if row[3] in _TERMINAL_CLOSE and row[4]}
    for cid, _bid, status, _sym, _payload in list_intents(path):
        if not is_close_cid(cid, structure_id):
            continue
        if cid in terminal_cids:
            continue
        if status in _UNRESOLVED_CLOSE:
            return ("ambiguous", cid)
    return None


def close_structure(
    structure_id: int,
    open_payload: dict,
    *,
    path: Path = DEFAULT_PATH,
    submit_fn=None,
) -> dict | FailClosed:
    with _lock(structure_id):
        struct = get_structure(structure_id, path)
        if not struct:
            return FailClosed("missing_structure")
        try:
            st = StructureStatus(struct[2])
        except ValueError:
            return FailClosed("bad_status")
        if st is StructureStatus.CLOSED:
            return FailClosed("already_closed")
        if st is StructureStatus.CLOSING:
            return {"ok": True, "reason": "already_closing", "submitted": False}
        if st is StructureStatus.VOID:
            return FailClosed("void")
        if st not in {StructureStatus.OPEN, StructureStatus.NEEDS_REVIEW}:
            return FailClosed(f"not_open:{st}")

        unresolved = _unresolved_close(structure_id, path)
        if unresolved is not None:
            kind, data = unresolved
            if kind == "in_flight":
                cid = data[4] if isinstance(data, tuple) else data
                return {
                    "ok": True,
                    "reason": "existing_close",
                    "submitted": False,
                    "client_order_id": cid,
                }
            return FailClosed("unresolved_close")

        cid = next_close_client_order_id(structure_id, path)

        legs = open_payload.get("legs") or []
        if len(legs) != 2:
            update_structure(structure_id, status=StructureStatus.NEEDS_REVIEW.value, path=path)
            return FailClosed("refuse_non_atomic_close")

        quotes = None
        try:
            from execution.marks import fetch_quotes

            quotes = fetch_quotes(open_payload) or None
        except Exception:  # noqa: BLE001 - missing quotes fall back to inverted credit
            quotes = None

        try:
            open_qty = struct[3]
            qty = open_qty if open_qty and float(open_qty) > 0 else open_payload.get("qty")
            payload = close_mleg_payload(
                open_payload, client_order_id=cid, quotes=quotes, qty=qty
            )
        except ValueError as exc:
            update_structure(structure_id, status=StructureStatus.NEEDS_REVIEW.value, path=path)
            return FailClosed(str(exc))

        if submit_fn is None:
            return FailClosed("no_submit")

        from execution.executor import _extract_broker_order_id

        payload_json = json.dumps(payload)
        symbol = struct[1]

        def _persist(status: str, broker_order_id: str | None = None) -> None:
            insert_intent(
                cid,
                status=status,
                broker_order_id=broker_order_id,
                symbol=symbol,
                payload_json=payload_json,
                structure_id=structure_id,
                path=path,
            )

        # Persist enough to reconstruct the close if Alpaca accepts and we crash
        # before the order row is written.
        _persist(OrderStatus.SUBMITTING.value)

        try:
            result = submit_fn(payload)
        except TimeoutError:
            _persist(OrderStatus.NEEDS_REVIEW.value)
            update_structure(structure_id, status=StructureStatus.NEEDS_REVIEW.value, path=path)
            return FailClosed("ambiguous_timeout")
        except Exception:  # noqa: BLE001 - unknown broker error after a close attempt
            _persist(OrderStatus.NEEDS_REVIEW.value)
            update_structure(structure_id, status=StructureStatus.NEEDS_REVIEW.value, path=path)
            return FailClosed("broker_error")

        broker_order_id = _extract_broker_order_id(result)
        if not broker_order_id:
            _persist(OrderStatus.NEEDS_REVIEW.value)
            update_structure(structure_id, status=StructureStatus.NEEDS_REVIEW.value, path=path)
            return FailClosed("missing_broker_id")

        step_structure(st, StructureStatus.CLOSING)
        update_structure(structure_id, status=StructureStatus.CLOSING.value, path=path)
        insert_order(
            structure_id=structure_id,
            role="close",
            status=OrderStatus.WORKING.value,
            client_order_id=cid,
            broker_order_id=broker_order_id,
            qty=float(payload.get("qty") or 1),
            payload_json=payload_json,
            path=path,
        )
        _persist(OrderStatus.WORKING.value, broker_order_id)
        return {"ok": True, "submitted": True, "client_order_id": cid, "payload": payload}
