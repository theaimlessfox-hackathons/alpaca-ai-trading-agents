from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from config.states import OrderStatus, StructureStatus

ET = ZoneInfo("America/New_York")

DEFAULT_PATH = Path("logs/thetagate.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  verdict TEXT,
  reason TEXT,
  proposal_json TEXT,
  critic_json TEXT
);
CREATE TABLE IF NOT EXISTS structures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT,
  status TEXT NOT NULL,
  open_qty REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  structure_id INTEGER,
  role TEXT,
  status TEXT NOT NULL,
  client_order_id TEXT,
  broker_order_id TEXT,
  qty REAL,
  filled_qty REAL DEFAULT 0,
  payload_json TEXT,
  created_ts TEXT
);
CREATE TABLE IF NOT EXISTS intents (
  client_order_id TEXT PRIMARY KEY,
  broker_order_id TEXT,
  status TEXT,
  symbol TEXT,
  payload_json TEXT,
  structure_id INTEGER
);
CREATE TABLE IF NOT EXISTS equity_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  equity REAL,
  ts TEXT
);
CREATE TABLE IF NOT EXISTS positions_snapshot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payload TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payload TEXT
);
"""


def connect(path: Path = DEFAULT_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def create_all(path: Path = DEFAULT_PATH) -> None:
    con = connect(path)
    con.executescript(SCHEMA)
    # CREATE TABLE IF NOT EXISTS doesn't add columns to a table that already
    # exists from an older schema version -- migrate additive columns here so a
    # pre-existing local dev DB doesn't break when the schema grows.
    cols = {row[1] for row in con.execute("PRAGMA table_info(orders)")}
    if "payload_json" not in cols:
        con.execute("ALTER TABLE orders ADD COLUMN payload_json TEXT")
    if "created_ts" not in cols:
        con.execute("ALTER TABLE orders ADD COLUMN created_ts TEXT")
    eq_cols = {row[1] for row in con.execute("PRAGMA table_info(equity_history)")}
    if "ts" not in eq_cols:
        con.execute("ALTER TABLE equity_history ADD COLUMN ts TEXT")
    cycle_cols = {row[1] for row in con.execute("PRAGMA table_info(cycles)")}
    if "critic_json" not in cycle_cols:
        con.execute("ALTER TABLE cycles ADD COLUMN critic_json TEXT")
    intent_cols = {row[1] for row in con.execute("PRAGMA table_info(intents)")}
    if "symbol" not in intent_cols:
        con.execute("ALTER TABLE intents ADD COLUMN symbol TEXT")
    if "payload_json" not in intent_cols:
        con.execute("ALTER TABLE intents ADD COLUMN payload_json TEXT")
    if "structure_id" not in intent_cols:
        con.execute("ALTER TABLE intents ADD COLUMN structure_id INTEGER")
    con.commit()
    con.close()


def insert_cycle(
    symbol: str,
    verdict: str,
    reason: str,
    proposal_json: str = "",
    critic_json: str = "",
    path: Path = DEFAULT_PATH,
) -> int:
    con = connect(path)
    cur = con.execute(
        "INSERT INTO cycles(symbol, verdict, reason, proposal_json, critic_json) VALUES (?,?,?,?,?)",
        (symbol, verdict, reason, proposal_json, critic_json),
    )
    con.commit()
    cid = cur.lastrowid
    con.close()
    return int(cid)


def insert_intent(
    client_order_id: str,
    *,
    status: str,
    broker_order_id: str | None = None,
    symbol: str | None = None,
    payload_json: str | None = None,
    structure_id: int | None = None,
    path: Path = DEFAULT_PATH,
) -> None:
    con = connect(path)
    con.execute(
        "INSERT INTO intents(client_order_id, broker_order_id, status, symbol, payload_json, structure_id) "
        "VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(client_order_id) DO UPDATE SET status=excluded.status, "
        "broker_order_id=COALESCE(excluded.broker_order_id, intents.broker_order_id), "
        "symbol=COALESCE(excluded.symbol, intents.symbol), "
        "payload_json=COALESCE(excluded.payload_json, intents.payload_json), "
        "structure_id=COALESCE(excluded.structure_id, intents.structure_id)",
        (client_order_id, broker_order_id, status, symbol, payload_json, structure_id),
    )
    con.commit()
    con.close()


def get_intent(client_order_id: str, path: Path = DEFAULT_PATH) -> tuple | None:
    con = connect(path)
    row = con.execute(
        "SELECT client_order_id, broker_order_id, status FROM intents WHERE client_order_id=?",
        (client_order_id,),
    ).fetchone()
    con.close()
    return row


def get_intent_row(client_order_id: str, path: Path = DEFAULT_PATH) -> dict | None:
    con = connect(path)
    row = con.execute(
        "SELECT client_order_id, broker_order_id, status, symbol, payload_json, structure_id "
        "FROM intents WHERE client_order_id=?",
        (client_order_id,),
    ).fetchone()
    con.close()
    if not row:
        return None
    return {
        "client_order_id": row[0],
        "broker_order_id": row[1],
        "status": row[2],
        "symbol": row[3],
        "payload_json": row[4],
        "structure_id": row[5],
    }


def list_intents(path: Path = DEFAULT_PATH) -> list[tuple]:
    con = connect(path)
    rows = con.execute(
        "SELECT client_order_id, broker_order_id, status, symbol, payload_json FROM intents"
    ).fetchall()
    con.close()
    return list(rows)


def get_cycle(cid: int, path: Path = DEFAULT_PATH) -> tuple | None:
    con = connect(path)
    row = con.execute("SELECT id, symbol, verdict, reason FROM cycles WHERE id=?", (cid,)).fetchone()
    con.close()
    return row


def insert_equity(equity: float, path: Path = DEFAULT_PATH) -> None:
    con = connect(path)
    con.execute(
        "INSERT INTO equity_history(equity, ts) VALUES (?,?)",
        (equity, datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


def recent_equity(limit: int = 200, path: Path = DEFAULT_PATH) -> list[dict]:
    """Most-recent-first. `ts` is None for rows written before the column
    existed (pre-migration) -- callers should treat that as "unknown day"."""
    con = connect(path)
    rows = con.execute(
        "SELECT id, equity, ts FROM equity_history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return [{"id": r[0], "equity": r[1], "ts": r[2]} for r in rows]


def trading_session_date(ts: str | datetime | None = None) -> str | None:
    """US equity session date in America/New_York. UTC midnight would split
    an evening session across two calendar days — never use the UTC date."""
    if ts is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(ts, datetime):
        dt = ts
    else:
        text = str(ts).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET).date().isoformat()


def session_sod_and_start(path: Path = DEFAULT_PATH) -> tuple[float, float]:
    """(start-of-session equity, first-ever equity). Defaults 100_000."""
    con = connect(path)
    rows = con.execute("SELECT equity, ts FROM equity_history ORDER BY id ASC").fetchall()
    con.close()
    if not rows:
        return 100_000.0, 100_000.0
    start = float(rows[0][0])
    today = trading_session_date()
    same = [float(r[0]) for r in rows if r[1] and trading_session_date(r[1]) == today]
    # Never fall back to first-ever equity as today's SOD — that hides an
    # overnight/session-open loss against a grown account. Callers should
    # insert today's print first so `same` is nonempty.
    sod = same[0] if same else start
    return sod, start


def daily_pnl(path: Path = DEFAULT_PATH) -> float:
    """Latest equity minus the earliest snapshot on the same US session date.

    Reads the full equity_history table (not a 200-row window) so a long
    session cannot lose its start-of-day print.
    """
    con = connect(path)
    rows = con.execute("SELECT id, equity, ts FROM equity_history ORDER BY id ASC").fetchall()
    con.close()
    dated = [(r[1], trading_session_date(r[2])) for r in rows if r[2]]
    dated = [(eq, day) for eq, day in dated if day]
    if not dated:
        return 0.0
    today = dated[-1][1]
    same_day = [eq for eq, day in dated if day == today]
    if len(same_day) < 2:
        return 0.0
    return same_day[-1] - same_day[0]


def recent_cycles(symbol: str | None = None, limit: int = 5, path: Path = DEFAULT_PATH) -> list[dict]:
    """Most-recent-first. Pass symbol=None for a global chronological feed."""
    con = connect(path)
    if symbol is None:
        rows = con.execute(
            "SELECT id, verdict, reason, proposal_json, critic_json, symbol "
            "FROM cycles ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id, verdict, reason, proposal_json, critic_json, symbol "
            "FROM cycles WHERE symbol=? ORDER BY id DESC LIMIT ?",
            (symbol, limit),
        ).fetchall()
    con.close()
    return [
        {
            "id": r[0],
            "verdict": r[1],
            "reason": r[2],
            "proposal_json": r[3],
            "critic_json": r[4],
            "symbol": r[5],
        }
        for r in rows
    ]
