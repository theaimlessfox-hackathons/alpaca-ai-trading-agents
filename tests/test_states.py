from config.states import OrderStatus, StructureStatus, structure_after_entry_order
from execution.transitions import step_order, step_structure


def test_order_status_members():
    assert [s.value for s in OrderStatus] == [
        "INTENT",
        "SUBMITTING",
        "WORKING",
        "PARTIALLY_FILLED",
        "FILLED",
        "CANCEL_REQUESTED",
        "CANCELED",
        "REJECTED",
        "EXPIRED",
        "NEEDS_REVIEW",
    ]


def test_structure_status_members():
    assert [s.value for s in StructureStatus] == [
        "PENDING_ENTRY",
        "OPEN",
        "CLOSING",
        "CLOSED",
        "VOID",
        "NEEDS_REVIEW",
    ]
    assert not hasattr(StructureStatus, "CANCELED")


def test_no_structure_canceled():
    assert not hasattr(StructureStatus, "CANCELED")
    assert OrderStatus.CANCELED.value == "CANCELED"


def test_partial_then_cancel_leaves_open():
    assert structure_after_entry_order(OrderStatus.PARTIALLY_FILLED, 1) is StructureStatus.OPEN
    assert structure_after_entry_order(OrderStatus.CANCELED, 1) is StructureStatus.OPEN


def test_cancel_unfilled_voids_structure():
    assert structure_after_entry_order(OrderStatus.CANCELED, 0) is StructureStatus.VOID
    assert structure_after_entry_order(OrderStatus.EXPIRED, 0) is StructureStatus.VOID
    assert structure_after_entry_order(OrderStatus.REJECTED, 0) is StructureStatus.VOID


def test_needs_review_can_confirm_cancel_and_void():
    assert step_order(OrderStatus.NEEDS_REVIEW, OrderStatus.CANCELED) is OrderStatus.CANCELED
    assert step_structure(StructureStatus.NEEDS_REVIEW, StructureStatus.VOID) is StructureStatus.VOID
