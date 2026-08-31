"""Order and structure status are different machines. Do not collapse them."""

from __future__ import annotations

from enum import StrEnum


class OrderStatus(StrEnum):
    INTENT = "INTENT"
    SUBMITTING = "SUBMITTING"
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class StructureStatus(StrEnum):
    PENDING_ENTRY = "PENDING_ENTRY"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    VOID = "VOID"
    NEEDS_REVIEW = "NEEDS_REVIEW"


# Canceling an order is never a structure cancel.
assert not hasattr(StructureStatus, "CANCELED")


def structure_after_entry_order(order: OrderStatus, filled_qty: float) -> StructureStatus | None:
    """Map an entry order outcome to structure status. None = no structure yet."""
    if filled_qty > 0:
        return StructureStatus.OPEN
    if order in {OrderStatus.REJECTED, OrderStatus.EXPIRED, OrderStatus.CANCELED}:
        return StructureStatus.VOID
    if order in {
        OrderStatus.INTENT,
        OrderStatus.SUBMITTING,
        OrderStatus.WORKING,
        OrderStatus.CANCEL_REQUESTED,
    }:
        return StructureStatus.PENDING_ENTRY
    if order is OrderStatus.NEEDS_REVIEW:
        return StructureStatus.NEEDS_REVIEW
    return None
