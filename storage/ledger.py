"""Structures and orders as separate rows."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from config.states import OrderStatus, StructureStatus
from storage.db import DEFAULT_PATH, connect, create_all

_VISIBLE = (
    StructureStatus.OPEN.value,
    StructureStatus.PENDING_ENTRY.value,
    StructureStatus.CLOSING.value,
    StructureStatus.NEEDS_REVIEW.value,
)
_ACTIVE = (
    StructureStatus.OPEN.value,
    StructureStatus.CLOSING.value,
    StructureStatus.NEEDS_REVIEW.value,
)


def insert_structure(symbol: str, *, status: str = StructureStatus.PENDING_ENTRY.value, open_qty: float = 0, path: Path = DEFAULT_PATH) -> int:
    create_all(path)
    con = connect(path)
    cur = con.execute(
        "INSERT INTO structures(symbol, status, open_qty) VALUES (?,?,?)",
        (symbol, status, open_qty),
    )
    con.commit()
    sid = int(cur.lastrowid)
    con.close()
    return sid


def get_structure(sid: int, path: Path = DEFAULT_PATH) -> tuple | None:
    con = connect(path)
    row = con.execute("SELECT id, symbol, status, open_qty FROM structures WHERE id=?", (sid,)).fetchone()
    con.close()
    return row


def update_structure(sid: int, *, status: str | None = None, open_qty: float | None = None, path: Path = DEFAULT_PATH) -> None:
    row = get_structure(sid, path)
    if not row:
        raise KeyError(sid)
    st = status if status is not None else row[2]
    qty = row[3] if open_qty is None else open_qty
    con = connect(path)
    con.execute("UPDATE structures SET status=?, open_qty=? WHERE id=?", (st, qty, sid))
    con.commit()
    con.close()


def insert_order(
    *,
    structure_id: int,
    role: str,
    status: str,
    client_order_id: str,
    qty: float,
    filled_qty: float = 0,
    broker_order_id: str | None = None,
    payload_json: str | None = None,
    path: Path = DEFAULT_PATH,
) -> int:
    create_all(path)
    con = connect(path)
    cur = con.execute(
        "INSERT INTO orders(structure_id, role, status, client_order_id, broker_order_id, qty, filled_qty, payload_json, created_ts) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            structure_id,
            role,
            status,
            client_order_id,
            broker_order_id,
            qty,
            filled_qty,
            payload_json,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    con.commit()
    oid = int(cur.lastrowid)
    con.close()
    return oid


def get_order(oid: int, path: Path = DEFAULT_PATH) -> tuple | None:
    con = connect(path)
    row = con.execute(
        "SELECT id, structure_id, role, status, client_order_id, broker_order_id, qty, filled_qty FROM orders WHERE id=?",
        (oid,),
    ).fetchone()
    con.close()
    return row


def get_order_by_cid(client_order_id: str, path: Path = DEFAULT_PATH) -> tuple | None:
    con = connect(path)
    row = con.execute(
        "SELECT id, structure_id, role, status, client_order_id, broker_order_id, qty, filled_qty FROM orders WHERE client_order_id=?",
        (client_order_id,),
    ).fetchone()
    con.close()
    return row


def get_entry_payload(structure_id: int, path: Path = DEFAULT_PATH) -> dict | None:
    """The stored entry-order payload for a structure, so a later close/flatten
    can reconstruct what to close without depending on a caller's in-memory
    state (e.g. after a process restart, or a scheduler-triggered flatten that
    never built the payload itself)."""
    import json

    con = connect(path)
    row = con.execute(
        "SELECT payload_json FROM orders WHERE structure_id=? AND role='entry' ORDER BY id DESC LIMIT 1",
        (structure_id,),
    ).fetchone()
    con.close()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None


def update_order(oid: int, *, status: str | None = None, filled_qty: float | None = None, broker_order_id: str | None = None, path: Path = DEFAULT_PATH) -> None:
    row = get_order(oid, path)
    if not row:
        raise KeyError(oid)
    st = status if status is not None else row[3]
    fq = row[7] if filled_qty is None else filled_qty
    br = row[5] if broker_order_id is None else broker_order_id
    con = connect(path)
    con.execute("UPDATE orders SET status=?, filled_qty=?, broker_order_id=? WHERE id=?", (st, fq, br, oid))
    con.commit()
    con.close()


def _structures_in(statuses: tuple[str, ...], path: Path) -> list[tuple]:
    con = connect(path)
    rows = con.execute(
        "SELECT id, symbol, status, open_qty FROM structures WHERE status IN ({})".format(
            ",".join("?" * len(statuses))
        ),
        statuses,
    ).fetchall()
    con.close()
    return list(rows)


def open_structures(path: Path = DEFAULT_PATH) -> list[tuple]:
    """Dashboard/visible set: live, pending, closing, and unresolved. Not VOID/CLOSED."""
    return _structures_in(_VISIBLE, path)


def active_structures(path: Path = DEFAULT_PATH) -> list[tuple]:
    """Live Alpaca exposure: OPEN, CLOSING, NEEDS_REVIEW. Pending entries are not fills."""
    return _structures_in(_ACTIVE, path)


def pending_entries(path: Path = DEFAULT_PATH) -> list[tuple]:
    return _structures_in((StructureStatus.PENDING_ENTRY.value,), path)


def list_orders(
    path: Path = DEFAULT_PATH,
    *,
    statuses: tuple[str, ...] | None = None,
    role: str | None = None,
    structure_id: int | None = None,
) -> list[tuple]:
    con = connect(path)
    sql = "SELECT id, structure_id, role, status, client_order_id, broker_order_id, qty, filled_qty FROM orders"
    clauses: list[str] = []
    args: list = []
    if statuses:
        clauses.append("status IN ({})".format(",".join("?" * len(statuses))))
        args.extend(statuses)
    if role:
        clauses.append("role=?")
        args.append(role)
    if structure_id is not None:
        clauses.append("structure_id=?")
        args.append(structure_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    rows = con.execute(sql, args).fetchall()
    con.close()
    return list(rows)


def latest_close_order(structure_id: int, path: Path = DEFAULT_PATH) -> tuple | None:
    rows = list_orders(path, role="close", structure_id=structure_id)
    return rows[-1] if rows else None


def list_entry_orders_with_ts(
    path: Path = DEFAULT_PATH,
    *,
    statuses: tuple[str, ...] | None = None,
) -> list[tuple]:
    """(id, structure_id, status, client_order_id, broker_order_id, created_ts)."""
    con = connect(path)
    sql = (
        "SELECT id, structure_id, status, client_order_id, broker_order_id, created_ts "
        "FROM orders WHERE role='entry'"
    )
    args: list = []
    if statuses:
        sql += " AND status IN ({})".format(",".join("?" * len(statuses)))
        args.extend(statuses)
    rows = con.execute(sql, args).fetchall()
    con.close()
    return list(rows)
