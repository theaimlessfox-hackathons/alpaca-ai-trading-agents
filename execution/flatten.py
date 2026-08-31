"""019 — flatten_all. Does not import scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.states import OrderStatus, StructureStatus
from execution.close import FailClosed, close_structure
from storage.db import DEFAULT_PATH
from storage.ledger import (
    active_structures,
    get_entry_payload,
    get_structure,
    list_orders,
    open_structures,
    pending_entries,
)


@dataclass(frozen=True)
class FlattenResult:
    submitted: int = 0
    failed: int = 0
    skipped: int = 0
    already: int = 0
    canceled: int = 0
    cancel_unresolved: int = 0
    remaining: int = 0

    @property
    def complete(self) -> bool:
        return (
            self.failed == 0
            and self.skipped == 0
            and self.cancel_unresolved == 0
            and self.remaining == 0
        )

    def __int__(self) -> int:
        return self.submitted


_TERMINAL_ENTRY = {
    OrderStatus.FILLED.value,
    OrderStatus.CANCELED.value,
    OrderStatus.EXPIRED.value,
    OrderStatus.REJECTED.value,
}


def _remaining_halt_exposure(path: Path) -> int:
    """Pending entries plus live structures that are not yet CLOSING."""
    n = len(pending_entries(path))
    n += sum(1 for _sid, _sym, status, _qty in active_structures(path) if status != StructureStatus.CLOSING.value)
    return n


def _unresolved_entry_count(path: Path) -> int:
    return sum(1 for row in list_orders(path, role="entry") if row[3] not in _TERMINAL_ENTRY)


def flatten_all(
    reason: str,
    *,
    payloads: dict[int, dict],
    path: Path = DEFAULT_PATH,
    close_fn=close_structure,
    submit_fn=None,
    cancel_fn=None,
    lookup_fn=None,
) -> FlattenResult:
    """Kill/halt backstop: cancel working entries, reconcile, then flatten fills.

    `.complete` is true only when no pending entries remain, no live OPEN/
    NEEDS_REVIEW structures remain, and no cancel/close failed."""
    from execution.cancel import cancel_nonterminal_entries
    from execution.reconcile import reconcile_working
    from storage.logger import log_event

    canceled_ids, unresolved_ids = cancel_nonterminal_entries(
        path=path, cancel_fn=cancel_fn, lookup_fn=lookup_fn
    )
    reconcile_working(path=path, lookup_fn=lookup_fn)

    submitted = failed = skipped = already = 0
    for sid, sym, status, _qty in open_structures(path):
        if status in {
            StructureStatus.CLOSING.value,
            StructureStatus.CLOSED.value,
            StructureStatus.VOID.value,
            StructureStatus.PENDING_ENTRY.value,
        }:
            continue
        payload = payloads.get(sid) or get_entry_payload(sid, path)
        if not payload:
            skipped += 1
            log_event("flatten_skip_no_payload", reason=reason, structure_id=sid, symbol=sym)
            continue
        # Close only the reconciled fill, not the original requested size.
        struct = get_structure(sid, path)
        open_qty = struct[3] if struct else None
        if open_qty and float(open_qty) > 0:
            payload = {**payload, "qty": str(int(open_qty)) if float(open_qty) == int(open_qty) else str(open_qty)}
        try:
            result = close_fn(sid, payload, path=path, submit_fn=submit_fn)
        except TypeError:
            result = close_fn(sid, payload, path=path)
        if isinstance(result, FailClosed):
            failed += 1
            log_event(
                "flatten_close_failed",
                reason=reason,
                structure_id=sid,
                symbol=sym,
                detail=result.reason,
            )
        elif isinstance(result, dict) and result.get("submitted"):
            submitted += 1
        else:
            already += 1

    remaining = _remaining_halt_exposure(path)
    cancel_unresolved = _unresolved_entry_count(path)
    out = FlattenResult(
        submitted=submitted,
        failed=failed,
        skipped=skipped,
        already=already,
        canceled=len(canceled_ids),
        cancel_unresolved=cancel_unresolved,
        remaining=remaining,
    )
    if not out.complete:
        log_event(
            "flatten_incomplete",
            reason=reason,
            submitted=submitted,
            failed=failed,
            skipped=skipped,
            canceled=out.canceled,
            cancel_unresolved=cancel_unresolved,
            remaining=remaining,
        )
    return out
