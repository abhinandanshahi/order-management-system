import pytest

from app.domain.enums import OrderStatus
from app.domain.exceptions import InvalidStateTransition
from app.domain.order_state_machine import ensure_transition_allowed


def test_valid_order_journey_transitions() -> None:
    ensure_transition_allowed(OrderStatus.NEW, OrderStatus.VALIDATED)
    ensure_transition_allowed(OrderStatus.VALIDATED, OrderStatus.ROUTED)
    ensure_transition_allowed(OrderStatus.ROUTED, OrderStatus.PARTIALLY_FILLED)
    ensure_transition_allowed(OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED)


def test_cancel_pending_can_be_filled_before_cancel_acknowledgement() -> None:
    ensure_transition_allowed(OrderStatus.CANCEL_PENDING, OrderStatus.FILLED)


def test_terminal_order_rejects_further_transition() -> None:
    with pytest.raises(InvalidStateTransition):
        ensure_transition_allowed(OrderStatus.FILLED, OrderStatus.CANCELLED)
