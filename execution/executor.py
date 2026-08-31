"""Executor. Never imports agents.llm. place_option_order only via execution.broker when live=True."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

from agents.schemas import CriticNote, TradeProposal
from config.states import OrderStatus, StructureStatus
from execution.account_guard import assert_can_submit, resolve_account_id_sync
from risk.engine import Leg, PortfolioView, ProposalView, validate
from risk.kill_switch import is_killed
from risk.types import Veto
from storage.db import get_intent, insert_cycle, insert_intent
from strategy.structures import to_mleg_payload

_UNRESOLVED = {
    OrderStatus.SUBMITTING.value,
    OrderStatus.NEEDS_REVIEW.value,
    OrderStatus.WORKING.value,
}


def _extract_broker_order_id(result) -> str | None:
    """Fail closed: unrecognized shapes return None. Callers must not record
    WORKING or allow a retry when this is None."""
    if isinstance(result, str):
        text = result.strip()
        if text and " " not in text and not text.lower().startswith("error"):
            return text
        return None
    if not isinstance(result, dict):
        return None
    data = result.get("data") if isinstance(result.get("data"), dict) else result
    for blob in (data, result):
        if not isinstance(blob, dict):
            continue
        for key in ("id", "order_id", "broker_order_id"):
            v = blob.get(key)
            if v:
                return str(v)
        order = blob.get("order")
        if isinstance(order, dict) and order.get("id"):
            return str(order["id"])
    return None


def _view(p: TradeProposal) -> ProposalView:
    return ProposalView(
        symbol=p.symbol,
        structure=p.structure,
        dte=p.dte,
        qty=p.qty,
        est_max_loss=p.est_max_loss,
        expiration=p.expiration,
        legs=[
            Leg(lg.side, lg.right, lg.strike, lg.delta, lg.bid, lg.ask, lg.iv, lg.occ_symbol)
            for lg in p.legs
        ],
    )


def client_order_id(proposal: TradeProposal) -> str:
    return "tg-" + hashlib.sha256(proposal.model_dump_json().encode()).hexdigest()[:24]


def dry_run(
    proposal: TradeProposal,
    book: PortfolioView,
    *,
    live: bool = False,
    account_id: str | None = None,
    db_path: Path | None = None,
    lookup_existing: Callable[[str], str | None] | None = None,
    critic: CriticNote | None = None,
) -> dict:
    kwargs = {} if db_path is None else {"path": db_path}
    critic_json = critic.model_dump_json() if critic is not None else ""

    if is_killed():
        insert_cycle(proposal.symbol, "veto", "kill_switch", critic_json=critic_json, **kwargs)
        return {"ok": False, "reason": "kill_switch", "submitted": False}

    verdict = validate(_view(proposal), book)
    if isinstance(verdict, Veto):
        insert_cycle(
            proposal.symbol, "veto", verdict.reason, proposal.model_dump_json(), critic_json, **kwargs
        )
        return {"ok": False, "reason": verdict.reason, "submitted": False}

    cid = client_order_id(proposal)
    existing = get_intent(cid, **kwargs)
    if existing and existing[1]:
        insert_cycle(proposal.symbol, "duplicate", "existing_broker_id", **kwargs)
        return {
            "ok": True,
            "submitted": False,
            "reason": "existing_broker_id",
            "client_order_id": cid,
            "broker_order_id": existing[1],
        }
    if existing and existing[2] in _UNRESOLVED:
        insert_cycle(proposal.symbol, "duplicate", "unresolved_intent", **kwargs)
        return {
            "ok": False,
            "submitted": False,
            "reason": "unresolved_intent",
            "client_order_id": cid,
        }

    if lookup_existing is not None:
        found = lookup_existing(cid)
        if found:
            insert_intent(
                cid,
                status=OrderStatus.NEEDS_REVIEW.value,
                broker_order_id=found,
                symbol=proposal.symbol,
                **kwargs,
            )
            return {
                "ok": True,
                "submitted": False,
                "reason": "broker_duplicate",
                "client_order_id": cid,
                "broker_order_id": found,
            }

    view = _view(proposal)
    payload = to_mleg_payload(
        view, client_order_id=cid, expiration=date.fromisoformat(proposal.expiration[:10])
    )
    payload_json = json.dumps(payload)
    insert_intent(
        cid,
        status=OrderStatus.INTENT.value,
        symbol=proposal.symbol,
        payload_json=payload_json,
        **kwargs,
    )

    if live:
        resolved_account = account_id or resolve_account_id_sync()
        assert_can_submit(account_id=resolved_account)
        from storage.ledger import insert_order, insert_structure, update_order, update_structure

        # Ledger first: an accepted broker order with no structure/order rows
        # cannot be closed or flattened. Persist PENDING/SUBMITTING before I/O.
        sid = insert_structure(proposal.symbol, status=StructureStatus.PENDING_ENTRY.value, **kwargs)
        oid = insert_order(
            structure_id=sid,
            role="entry",
            status=OrderStatus.SUBMITTING.value,
            client_order_id=cid,
            qty=proposal.qty,
            payload_json=payload_json,
            **kwargs,
        )
        insert_intent(
            cid,
            status=OrderStatus.SUBMITTING.value,
            symbol=proposal.symbol,
            payload_json=payload_json,
            structure_id=sid,
            **kwargs,
        )
        from execution.broker import place_option_order_sync

        def _ambiguous(reason: str) -> dict:
            insert_intent(cid, status=OrderStatus.NEEDS_REVIEW.value, symbol=proposal.symbol, **kwargs)
            update_order(oid, status=OrderStatus.NEEDS_REVIEW.value, **kwargs)
            update_structure(sid, status=StructureStatus.NEEDS_REVIEW.value, **kwargs)
            insert_cycle(proposal.symbol, "needs_review", reason, critic_json=critic_json, **kwargs)
            return {
                "ok": False,
                "reason": reason,
                "submitted": False,
                "client_order_id": cid,
                "structure_id": sid,
            }

        try:
            result = place_option_order_sync(payload)
        except TimeoutError:
            return _ambiguous("ambiguous_timeout")
        except Exception:  # noqa: BLE001 - any broker error after persist is unresolved
            return _ambiguous("broker_error")

        broker_order_id = _extract_broker_order_id(result)
        if not broker_order_id:
            return _ambiguous("missing_broker_id")

        insert_intent(
            cid,
            status=OrderStatus.WORKING.value,
            broker_order_id=broker_order_id,
            symbol=proposal.symbol,
            payload_json=payload_json,
            **kwargs,
        )
        update_order(
            oid,
            status=OrderStatus.WORKING.value,
            broker_order_id=broker_order_id,
            **kwargs,
        )

        insert_cycle(
            proposal.symbol,
            "submitted",
            "ok",
            json.dumps(
                {
                    "client_order_id": cid,
                    "broker_order_id": broker_order_id,
                    "structure_id": sid,
                    "thesis": proposal.thesis,
                }
            ),
            critic_json,
            **kwargs,
        )
        return {
            "ok": True,
            "submitted": True,
            "client_order_id": cid,
            "broker_order_id": broker_order_id,
            "structure_id": sid,
            "result": str(result)[:200],
        }

    insert_cycle(
        proposal.symbol,
        "approve_dry",
        "ok",
        json.dumps({"client_order_id": cid, "thesis": proposal.thesis}),
        critic_json,
        **kwargs,
    )
    return {
        "ok": True,
        "client_order_id": cid,
        "payload": payload,
        "live": False,
        "submitted": False,
    }
