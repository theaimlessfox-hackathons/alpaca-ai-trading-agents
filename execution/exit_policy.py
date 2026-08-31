"""018 — decide whether to close. Does not submit."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import get_settings
from execution.close import FailClosed, close_structure


@dataclass(frozen=True)
class ExitOutcome:
    trigger: str
    submitted: bool
    reason: str | None = None
    client_order_id: str | None = None


def evaluate_exits(
    *,
    structure_id: int,
    credit: float,
    mark: float,
    structure_status: str,
    regime_stand_down: str | None,
    open_payload: dict,
    close_fn=close_structure,
    submit_fn=None,
) -> ExitOutcome | None:
    if structure_status in {"CLOSING", "CLOSED"}:
        return None
    s = get_settings()

    def _close() -> ExitOutcome:
        trigger = "pending"
        try:
            result = close_fn(structure_id, open_payload, submit_fn=submit_fn)
        except TypeError:
            result = close_fn(structure_id, open_payload)
        if isinstance(result, FailClosed):
            return ExitOutcome(trigger, False, result.reason)
        if isinstance(result, dict):
            return ExitOutcome(
                trigger,
                bool(result.get("submitted")),
                result.get("reason"),
                result.get("client_order_id"),
            )
        return ExitOutcome(trigger, False, "unknown_close_result")

    if credit > 0 and mark <= credit * (1 - s.take_profit_frac):
        out = _close()
        return ExitOutcome("take_profit", out.submitted, out.reason, out.client_order_id)
    if credit > 0 and mark >= credit * s.stop_mult:
        out = _close()
        return ExitOutcome("stop", out.submitted, out.reason, out.client_order_id)
    if regime_stand_down:
        out = _close()
        return ExitOutcome("regime", out.submitted, out.reason, out.client_order_id)
    return None
