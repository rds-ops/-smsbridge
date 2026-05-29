from __future__ import annotations

from typing import Final


class OrderStatus:
    CREATED: Final = "created"
    WAITING_SMS: Final = "waiting_sms"
    SMS_RECEIVED: Final = "sms_received"
    COMPLETED: Final = "completed"
    CANCELLED: Final = "cancelled"
    EXPIRED: Final = "expired"
    FAILED: Final = "failed"
    REFUNDED: Final = "refunded"


TERMINAL_STATUSES: Final = {
    OrderStatus.COMPLETED,
    OrderStatus.CANCELLED,
    OrderStatus.EXPIRED,
    OrderStatus.FAILED,
    OrderStatus.REFUNDED,
}

ACTIVE_STATUSES: Final = {
    OrderStatus.CREATED,
    OrderStatus.WAITING_SMS,
    OrderStatus.SMS_RECEIVED,
}

ALLOWED_TRANSITIONS: Final = {
    OrderStatus.CREATED: {
        OrderStatus.WAITING_SMS,
    },
    OrderStatus.WAITING_SMS: {
        OrderStatus.SMS_RECEIVED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
        OrderStatus.FAILED,
        OrderStatus.REFUNDED,
    },
    OrderStatus.SMS_RECEIVED: {
        OrderStatus.COMPLETED,
        OrderStatus.CANCELLED,
        OrderStatus.REFUNDED,
    },
    # Current admin refund cleanup can mark an already-refunded failed order as refunded.
    OrderStatus.FAILED: {
        OrderStatus.REFUNDED,
    },
}


class InvalidOrderTransition(ValueError):
    pass


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def validate_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise InvalidOrderTransition(f"Invalid order status transition: {current} -> {target}")


def transition_order(order, target_status: str, *, reason: str | None = None) -> None:
    _ = reason
    validate_transition(order.status, target_status)
    order.status = target_status
