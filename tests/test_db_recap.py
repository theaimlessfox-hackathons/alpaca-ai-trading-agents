from pathlib import Path

import pytest

from storage.db import create_all, daily_pnl, insert_cycle, insert_equity, recent_cycles, recent_equity


@pytest.fixture()
def db_path(tmp_path) -> Path:
    p = tmp_path / "test.db"
    create_all(p)
    return p


def test_recent_cycles_empty_when_no_rows(db_path):
    assert recent_cycles("SPY", path=db_path) == []


def test_recent_cycles_most_recent_first(db_path):
    insert_cycle("SPY", "veto", "wide_bid_ask", path=db_path)
    insert_cycle("SPY", "veto", "short_delta", path=db_path)
    insert_cycle("SPY", "approve_dry", "ok", path=db_path)

    rows = recent_cycles("SPY", path=db_path)
    assert [r["reason"] for r in rows] == ["ok", "short_delta", "wide_bid_ask"]


def test_recent_cycles_filters_by_symbol(db_path):
    insert_cycle("SPY", "veto", "wide_bid_ask", path=db_path)
    insert_cycle("QQQ", "veto", "iv", path=db_path)
    rows = recent_cycles("SPY", path=db_path)
    assert len(rows) == 1
    assert rows[0]["reason"] == "wide_bid_ask"


def test_recent_cycles_respects_limit(db_path):
    for i in range(10):
        insert_cycle("SPY", "veto", f"reason{i}", path=db_path)
    rows = recent_cycles("SPY", limit=3, path=db_path)
    assert len(rows) == 3


def test_insert_equity_stamps_a_timestamp(db_path):
    insert_equity(100_000.0, path=db_path)
    rows = recent_equity(path=db_path)
    assert len(rows) == 1
    assert rows[0]["equity"] == 100_000.0
    assert rows[0]["ts"] is not None


def test_recent_equity_most_recent_first(db_path):
    insert_equity(100_000.0, path=db_path)
    insert_equity(100_500.0, path=db_path)
    rows = recent_equity(path=db_path)
    assert [r["equity"] for r in rows] == [100_500.0, 100_000.0]


def test_daily_pnl_zero_with_no_snapshots(db_path):
    assert daily_pnl(path=db_path) == 0.0


def test_daily_pnl_zero_with_only_one_snapshot(db_path):
    insert_equity(100_000.0, path=db_path)
    assert daily_pnl(path=db_path) == 0.0


def test_daily_pnl_compares_against_earliest_same_day_snapshot(db_path):
    from storage.db import connect

    con = connect(db_path)
    for equity, ts in [
        (100_000.0, "2026-08-31T13:30:00+00:00"),
        (100_300.0, "2026-08-31T14:00:00+00:00"),
        (99_800.0, "2026-08-31T15:00:00+00:00"),
    ]:
        con.execute("INSERT INTO equity_history(equity, ts) VALUES (?,?)", (equity, ts))
    con.commit()
    con.close()
    assert daily_pnl(path=db_path) == 99_800.0 - 100_000.0


def test_daily_pnl_ignores_snapshots_from_a_different_day(db_path):
    con_path = db_path
    from storage.db import connect

    con = connect(con_path)
    con.execute("INSERT INTO equity_history(equity, ts) VALUES (?,?)", (100_000.0, "2026-08-30T15:00:00+00:00"))
    con.execute("INSERT INTO equity_history(equity, ts) VALUES (?,?)", (100_900.0, "2026-08-31T15:00:00+00:00"))
    con.commit()
    con.close()
    # only one row on 2026-08-31, so daily_pnl has nothing same-day to compare against
    assert daily_pnl(path=db_path) == 0.0


def test_daily_pnl_uses_et_session_not_utc_date(db_path):
    from storage.db import connect

    con = connect(db_path)
    # 8pm ET Aug 31 is Sep 1 00:00 UTC — these must still be the same session.
    con.execute(
        "INSERT INTO equity_history(equity, ts) VALUES (?,?)",
        (100_000.0, "2026-08-31T16:00:00-04:00"),
    )
    con.execute(
        "INSERT INTO equity_history(equity, ts) VALUES (?,?)",
        (100_400.0, "2026-09-01T00:00:00+00:00"),
    )
    con.commit()
    con.close()
    assert daily_pnl(path=db_path) == 400.0


def test_daily_pnl_reads_beyond_recent_window(db_path):
    from storage.db import connect

    con = connect(db_path)
    con.execute(
        "INSERT INTO equity_history(equity, ts) VALUES (?,?)",
        (100_000.0, "2026-08-31T13:30:00+00:00"),
    )
    for i in range(250):
        con.execute(
            "INSERT INTO equity_history(equity, ts) VALUES (?,?)",
            (100_000.0 + i, "2026-08-31T14:00:00+00:00"),
        )
    con.execute(
        "INSERT INTO equity_history(equity, ts) VALUES (?,?)",
        (99_500.0, "2026-08-31T15:00:00+00:00"),
    )
    con.commit()
    con.close()
    assert daily_pnl(path=db_path) == 99_500.0 - 100_000.0


def test_recent_cycles_global_is_chronological(db_path):
    insert_cycle("SPY", "veto", "old_spy", path=db_path)
    insert_cycle("QQQ", "approve_dry", "new_qqq", path=db_path)
    insert_cycle("IWM", "veto", "newest_iwm", path=db_path)
    rows = recent_cycles(limit=10, path=db_path)
    assert [r["reason"] for r in rows] == ["newest_iwm", "new_qqq", "old_spy"]
