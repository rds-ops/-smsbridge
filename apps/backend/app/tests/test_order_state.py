from __future__ import annotations

import pytest

from app.services.order_state import (
    ACTIVE_STATUSES,
    InvalidOrderTransition,
    OrderStatus,
    TERMINAL_STATUSES,
    can_transition,
    is_terminal,
    transition_order,
    validate_transition,
)


class DummyOrder:
    def __init__(self, status: str):
        self.status = status


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.CREATED, OrderStatus.WAITING_SMS),
        (OrderStatus.WAITING_SMS, OrderStatus.SMS_RECEIVED),
        (OrderStatus.WAITING_SMS, OrderStatus.CANCELLED),
        (OrderStatus.WAITING_SMS, OrderStatus.EXPIRED),
        (OrderStatus.WAITING_SMS, OrderStatus.FAILED),
        (OrderStatus.WAITING_SMS, OrderStatus.REFUNDED),
        (OrderStatus.SMS_RECEIVED, OrderStatus.COMPLETED),
        (OrderStatus.SMS_RECEIVED, OrderStatus.CANCELLED),
        (OrderStatus.SMS_RECEIVED, OrderStatus.REFUNDED),
        (OrderStatus.FAILED, OrderStatus.REFUNDED),
    ],
)
def test_valid_order_transitions_pass(current, target):
    validate_transition(current, target)
    assert can_transition(current, target)


def test_transition_order_updates_status_without_committing():
    order = DummyOrder(OrderStatus.CREATED)

    transition_order(order, OrderStatus.WAITING_SMS, reason="test")

    assert order.status == OrderStatus.WAITING_SMS


def test_invalid_order_transition_raises_clear_exception():
    with pytest.raises(InvalidOrderTransition, match="Invalid order status transition: waiting_sms -> completed"):
        validate_transition(OrderStatus.WAITING_SMS, OrderStatus.COMPLETED)


@pytest.mark.parametrize("status", TERMINAL_STATUSES)
def test_terminal_statuses_do_not_transition_back_to_active_statuses(status):
    assert is_terminal(status)
    for active_status in ACTIVE_STATUSES:
        assert not can_transition(status, active_status)
