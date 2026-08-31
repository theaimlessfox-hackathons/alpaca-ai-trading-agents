from pathlib import Path

from agents.schemas import TradeProposal
from execution.executor import client_order_id, dry_run
from risk.engine import PortfolioView
from risk.kill_switch import set_kill_switch
from storage.db import create_all, get_intent, insert_intent


def _proposal(**kw) -> TradeProposal:
    data = {
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
    data.update(kw)
    return TradeProposal.model_validate(data)


def test_dry_run_no_submit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("logs").mkdir()
    db = Path("logs/thetagate.db")
    create_all(db)
    out = dry_run(_proposal(), PortfolioView(nav=100_000), live=False, db_path=db)
    assert out["ok"] is True
    assert out["submitted"] is False
    assert out["live"] is False
    assert out["payload"]["order_class"] == "mleg"
    assert len(out["payload"]["legs"]) == 2
    intent = get_intent(out["client_order_id"], path=db)
    assert intent is not None
    assert intent[2] == "INTENT"


def test_same_hash_same_id():
    p = _proposal()
    assert client_order_id(p) == client_order_id(p)


def test_veto_stored(tmp_path):
    db = tmp_path / "t.db"
    create_all(db)
    out = dry_run(_proposal(symbol="NVDA"), PortfolioView(nav=100_000), db_path=db)
    assert out["ok"] is False
    assert out["submitted"] is False
    assert out["reason"] == "universe"


def test_kill_switch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("logs").mkdir()
    db = Path("logs/thetagate.db")
    create_all(db)
    set_kill_switch(True)
    out = dry_run(_proposal(), PortfolioView(nav=100_000), db_path=db)
    assert out["reason"] == "kill_switch"
    assert out["submitted"] is False
    set_kill_switch(False)


def test_existing_broker_id_no_submit(tmp_path):
    db = tmp_path / "t.db"
    create_all(db)
    p = _proposal()
    cid = client_order_id(p)
    insert_intent(cid, status="WORKING", broker_order_id="brk-1", path=db)
    out = dry_run(p, PortfolioView(nav=100_000), db_path=db)
    assert out["submitted"] is False
    assert out["reason"] == "existing_broker_id"


def test_lookup_existing_no_duplicate(tmp_path):
    db = tmp_path / "t.db"
    create_all(db)
    p = _proposal()
    out = dry_run(
        p,
        PortfolioView(nav=100_000),
        db_path=db,
        lookup_existing=lambda _cid: "brk-alpaca",
    )
    assert out["submitted"] is False
    assert out["reason"] == "broker_duplicate"


def _enable_live(monkeypatch, account_id="PA-TEST"):
    from config.settings import Settings

    s = Settings(expected_account_id=account_id, alpaca_paper_trade=True, alpaca_account_role="sandbox")
    monkeypatch.setattr("execution.account_guard.get_settings", lambda: s)
    monkeypatch.setattr("execution.executor.resolve_account_id_sync", lambda: account_id)
    return s


def test_live_submit_records_broker_order_id_for_idempotency(tmp_path, monkeypatch):
    """Regression test: the live path used to call insert_intent without a
    broker_order_id, so the existing_broker_id duplicate-guard could never
    fire for a real submit."""
    db = tmp_path / "t.db"
    create_all(db)
    _enable_live(monkeypatch)
    monkeypatch.setattr("execution.broker.place_option_order_sync", lambda payload: {"id": "brk-live-1"})

    p = _proposal()
    out = dry_run(p, PortfolioView(nav=100_000), live=True, db_path=db)
    assert out["submitted"] is True
    assert out["broker_order_id"] == "brk-live-1"

    intent = get_intent(out["client_order_id"], path=db)
    assert intent[1] == "brk-live-1"

    # a second call with the identical proposal must now be caught as a duplicate
    out2 = dry_run(p, PortfolioView(nav=100_000), live=True, db_path=db)
    assert out2["submitted"] is False
    assert out2["reason"] == "existing_broker_id"


def test_live_submit_creates_structure_and_entry_order(tmp_path, monkeypatch):
    """Regression test: nothing previously created a structures/orders row for a
    live entry, so close_structure/flatten_all had nothing to act on."""
    from storage.ledger import get_entry_payload, get_structure

    db = tmp_path / "t.db"
    create_all(db)
    _enable_live(monkeypatch)
    monkeypatch.setattr("execution.broker.place_option_order_sync", lambda payload: {"id": "brk-live-2"})

    out = dry_run(_proposal(), PortfolioView(nav=100_000), live=True, db_path=db)
    sid = out["structure_id"]
    struct = get_structure(sid, db)
    assert struct is not None
    assert struct[2] == "PENDING_ENTRY"

    payload = get_entry_payload(sid, db)
    assert payload is not None
    assert payload["order_class"] == "mleg"
    assert len(payload["legs"]) == 2


def test_live_submit_fails_closed_when_account_cannot_be_resolved(tmp_path, monkeypatch):
    """EXPECTED_ACCOUNT_ID configured + resolution fails => raise, not silently proceed."""
    import execution.executor as executor_mod
    from config.settings import Settings
    from execution.account_guard import AccountGuardError

    db = tmp_path / "t.db"
    create_all(db)
    monkeypatch.setattr(executor_mod, "resolve_account_id_sync", lambda: None)
    monkeypatch.setenv("EXPECTED_ACCOUNT_ID", "PA-REAL-ACCOUNT")
    from config.settings import get_settings

    get_settings.cache_clear()
    try:
        import pytest

        with pytest.raises(AccountGuardError):
            dry_run(_proposal(), PortfolioView(nav=100_000), live=True, db_path=db)
    finally:
        get_settings.cache_clear()


def test_dry_run_persists_critic_note(tmp_path):
    from agents.schemas import CriticNote
    from storage.db import recent_cycles

    db = tmp_path / "t.db"
    create_all(db)
    note = CriticNote(rebuttal="might not hold through CPI", invalidation=["CPI surprise"])
    dry_run(_proposal(), PortfolioView(nav=100_000), db_path=db, critic=note)
    rows = recent_cycles("SPY", path=db)
    assert rows
    assert rows[0]["critic_json"]
    assert "CPI surprise" in rows[0]["critic_json"]


def test_dry_run_veto_also_persists_critic_note(tmp_path):
    from agents.schemas import CriticNote
    from storage.db import recent_cycles

    db = tmp_path / "t.db"
    create_all(db)
    note = CriticNote(rebuttal="bad idea", invalidation=["always"])
    dry_run(_proposal(symbol="NVDA"), PortfolioView(nav=100_000), db_path=db, critic=note)
    rows = recent_cycles("NVDA", path=db)
    assert rows[0]["verdict"] == "veto"
    assert "bad idea" in rows[0]["critic_json"]


def test_executor_does_not_import_llm():
    src = Path("execution/executor.py").read_text()
    assert "import agents.llm" not in src
    assert "from agents.llm" not in src
    assert "call_tool(\"place_option_order\"" not in src
    assert "call_tool('place_option_order'" not in src


def test_live_submit_uses_proposal_expiration(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    create_all(db)
    _enable_live(monkeypatch)
    seen = {}

    def fake_place(payload):
        seen["payload"] = payload
        return {"id": "brk-exp"}

    monkeypatch.setattr("execution.broker.place_option_order_sync", fake_place)
    dry_run(_proposal(expiration="2026-10-16"), PortfolioView(nav=100_000), live=True, db_path=db)
    assert "261016" in seen["payload"]["legs"][0]["symbol"]


def test_live_submit_missing_broker_id_is_needs_review(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    create_all(db)
    _enable_live(monkeypatch)
    monkeypatch.setattr("execution.broker.place_option_order_sync", lambda payload: {"status": "accepted"})
    p = _proposal()
    out = dry_run(p, PortfolioView(nav=100_000), live=True, db_path=db)
    assert out["submitted"] is False
    assert out["reason"] == "missing_broker_id"
    intent = get_intent(out["client_order_id"], path=db)
    assert intent[2] == "NEEDS_REVIEW"
    out2 = dry_run(p, PortfolioView(nav=100_000), live=True, db_path=db)
    assert out2["submitted"] is False
    assert out2["reason"] == "unresolved_intent"


def test_live_submit_broker_error_is_needs_review(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    create_all(db)
    _enable_live(monkeypatch)

    def boom(_payload):
        raise RuntimeError("connection reset")

    monkeypatch.setattr("execution.broker.place_option_order_sync", boom)
    p = _proposal()
    out = dry_run(p, PortfolioView(nav=100_000), live=True, db_path=db)
    assert out["submitted"] is False
    assert out["reason"] == "broker_error"
    intent = get_intent(client_order_id(p), path=db)
    assert intent[2] == "NEEDS_REVIEW"
    out2 = dry_run(p, PortfolioView(nav=100_000), live=True, db_path=db)
    assert out2["submitted"] is False
    assert out2["reason"] == "unresolved_intent"
