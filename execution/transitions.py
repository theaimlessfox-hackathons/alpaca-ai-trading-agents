from __future__ import annotations

from config.states import OrderStatus, StructureStatus

ORDER_OK = {
    OrderStatus.INTENT: {
        OrderStatus.SUBMITTING,
        OrderStatus.WORKING,
        OrderStatus.REJECTED,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.NEEDS_REVIEW,
    },
    OrderStatus.SUBMITTING: {
        OrderStatus.WORKING,
        OrderStatus.REJECTED,
        OrderStatus.NEEDS_REVIEW,
        OrderStatus.CANCEL_REQUESTED,
    },
    OrderStatus.WORKING: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_REQUESTED,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.REJECTED,
        OrderStatus.NEEDS_REVIEW,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.FILLED,
        OrderStatus.CANCEL_REQUESTED,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.NEEDS_REVIEW,
    },
    OrderStatus.CANCEL_REQUESTED: {
        OrderStatus.CANCELED,
        OrderStatus.FILLED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.WORKING,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
        OrderStatus.NEEDS_REVIEW,
    },
}

STRUCT_OK = {
    StructureStatus.PENDING_ENTRY: {
        StructureStatus.OPEN,
        StructureStatus.NEEDS_REVIEW,
        StructureStatus.VOID,
    },
    StructureStatus.OPEN: {StructureStatus.CLOSING, StructureStatus.NEEDS_REVIEW},
    StructureStatus.CLOSING: {StructureStatus.CLOSED, StructureStatus.OPEN, StructureStatus.NEEDS_REVIEW},
    StructureStatus.NEEDS_REVIEW: {
        StructureStatus.CLOSING,
        StructureStatus.OPEN,
        StructureStatus.CLOSED,
        StructureStatus.VOID,
    },
}


class IllegalTransition(ValueError):
    pass


def step_order(cur: OrderStatus, nxt: OrderStatus) -> OrderStatus:
    if cur == nxt:
        return cur
    if nxt not in ORDER_OK.get(cur, set()):
        raise IllegalTransition(f"order {cur} -> {nxt}")
    return nxt


def step_structure(cur: StructureStatus, nxt: StructureStatus) -> StructureStatus:
    if cur == nxt:
        return cur
    if nxt not in STRUCT_OK.get(cur, set()):
        raise IllegalTransition(f"structure {cur} -> {nxt}")
    return nxt
