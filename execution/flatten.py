"""019 — flatten_all. Does not import scheduler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.states import StructureStatus
from execution.close import FailClosed, close_structure
from storage.db import DEFAULT_PATH
from storage.ledger import get_entry_payload, open_structures


@dataclass(frozen=True)
class FlattenResult:
    submitted: int = 0
    failed: int = 0
    skipped: int = 0
    already: int = 0

    @property
    def complete(self) -> bool:
        return self.failed == 0 and self.skipped == 0

    def __int__(self) -> int:
        return self.submitted


def flatten_all(
    reason: str,
    *,
    payloads: dict[int, dict],
    path: Path = DEFAULT_PATH,
    close_fn=close_structure,
    submit_fn=None,
) -> FlattenResult:
    """Kill-switch/halt backstop. Counts only closes that actually submitted
    (or were already in flight). FailClosed and missing payloads are failures
    / skips — callers must inspect `.complete`, not treat the call as success."""
    from storage.logger import log_event

    out = FlattenResult()
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
    out = FlattenResult(submitted=submitted, failed=failed, skipped=skipped, already=already)
    if not out.complete:
        log_event(
            "flatten_incomplete",
            reason=reason,
            submitted=submitted,
            failed=failed,
            skipped=skipped,
        )
    return out
