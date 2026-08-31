"""020 — restart recovery. Never invents a submit from an ambiguous state."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from config.states import OrderStatus, StructureStatus
from storage.db import DEFAULT_PATH, get_intent, get_intent_row, list_intents
from storage.ledger import get_order_by_cid, get_structure, insert_order, insert_structure, update_order, update_structure

_UNRESOLVED = {
    OrderStatus.SUBMITTING.value,
    OrderStatus.NEEDS_REVIEW.value,
    OrderStatus.CANCEL_REQUESTED.value,
}


def recover(client_order_id: str, *, path: Path = DEFAULT_PATH) -> str:
    intent = get_intent(client_order_id, path)
    order = get_order_by_cid(client_order_id, path)
    if intent and intent[2] in {
        OrderStatus.NEEDS_REVIEW.value,
        OrderStatus.CANCEL_REQUESTED.value,
        OrderStatus.SUBMITTING.value,
    }:
        return "wait_reconcile"
    if order and order[3] in {OrderStatus.SUBMITTING.value, OrderStatus.CANCEL_REQUESTED.value}:
        return "wait_reconcile"
    if order and order[3] == OrderStatus.CANCELED.value:
        return "order_canceled_not_structure_closed"
    return "ok"


def _lookup_broker(client_order_id: str):
    from tools.account_tools import get_order_by_client_id_sync

    return get_order_by_client_id_sync(client_order_id)


def _broker_id(found) -> str | None:
    from execution.executor import _extract_broker_order_id

    return _extract_broker_order_id(found)


def _qty_from_payload(payload_json: str | None) -> float:
    import json

    if not payload_json:
        return 1.0
    try:
        data = json.loads(payload_json)
        return float(data.get("qty") or 1)
    except (TypeError, ValueError, json.JSONDecodeError):
        return 1.0


def _close_structure_id(cid: str, row: dict) -> int | None:
    sid = row.get("structure_id")
    if sid is not None:
        try:
            return int(sid)
        except (TypeError, ValueError):
            pass
    # tg-close-{sid} or tg-close-{sid}-{attempt}
    parts = cid.split("-")
    if len(parts) >= 3 and parts[0] == "tg" and parts[1] == "close":
        try:
            return int(parts[2])
        except ValueError:
            return None
    return None


def _restore_order(cid: str, broker_id: str, path: Path) -> bool:
    order = get_order_by_cid(cid, path)
    if order:
        update_order(order[0], status=OrderStatus.WORKING.value, broker_order_id=broker_id, path=path)
        return True
    row = get_intent_row(cid, path)
    if not row or not row.get("payload_json"):
        return False
    is_close = cid.startswith("tg-close-")
    if is_close:
        sid = _close_structure_id(cid, row)
        if sid is None or not get_structure(sid, path):
            return False
        insert_order(
            structure_id=sid,
            role="close",
            status=OrderStatus.WORKING.value,
            client_order_id=cid,
            broker_order_id=broker_id,
            qty=_qty_from_payload(row["payload_json"]),
            payload_json=row["payload_json"],
            path=path,
        )
        struct = get_structure(sid, path)
        if struct and struct[2] == StructureStatus.OPEN.value:
            update_structure(sid, status=StructureStatus.CLOSING.value, path=path)
        return True
    if not row.get("symbol"):
        return False
    existing_sid = row.get("structure_id")
    if existing_sid is not None and get_structure(int(existing_sid), path):
        sid = int(existing_sid)
    else:
        sid = insert_structure(row["symbol"], status=StructureStatus.PENDING_ENTRY.value, path=path)
    insert_order(
        structure_id=sid,
        role="entry",
        status=OrderStatus.WORKING.value,
        client_order_id=cid,
        broker_order_id=broker_id,
        qty=_qty_from_payload(row["payload_json"]),
        payload_json=row["payload_json"],
        path=path,
    )
    return True


def recover_startup(
    *,
    path: Path = DEFAULT_PATH,
    lookup_fn: Callable[[str], object] | None = None,
) -> str:
    """Scan unresolved intents, query the broker, restore missing ledger rows.

    Returns "block_startup" when anything is still ambiguous after lookup —
    the scheduler must not open new risk on top of that.
    """
    blocked = False
    lookup = lookup_fn
    for cid, broker_id, status, _symbol, _payload in list_intents(path):
        needs_lookup = status in _UNRESOLVED or (not get_order_by_cid(cid, path) and (broker_id or status in _UNRESOLVED))
        if not needs_lookup:
            continue
        found = None
        try:
            found = lookup(cid) if lookup is not None else _lookup_broker(cid)
        except Exception:  # noqa: BLE001 - lookup failure leaves the intent unresolved
            found = None
        bid = _broker_id(found) or (str(broker_id) if broker_id else None)
        if bid and _restore_order(cid, bid, path):
            from storage.db import insert_intent

            insert_intent(cid, status=OrderStatus.WORKING.value, broker_order_id=bid, path=path)
            continue
        if status in _UNRESOLVED or (broker_id and not get_order_by_cid(cid, path)):
            blocked = True
    return "block_startup" if blocked else "ok"
