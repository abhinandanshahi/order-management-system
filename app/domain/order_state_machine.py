from app.domain.enums import OrderStatus
from app.domain.exceptions import InvalidStateTransition

ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.NEW: frozenset({OrderStatus.VALIDATED, OrderStatus.REJECTED}),
    OrderStatus.VALIDATED: frozenset(
        {OrderStatus.ROUTED, OrderStatus.REJECTED, OrderStatus.CANCEL_PENDING}
    ),
    OrderStatus.ROUTED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.REJECTED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
        }
    ),
    OrderStatus.CANCEL_PENDING: frozenset(
        {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
        }
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


OPEN_ORDER_STATUSES = frozenset(
    {
        OrderStatus.VALIDATED,
        OrderStatus.ROUTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCEL_PENDING,
    }
)

CANCELLABLE_ORDER_STATUSES = frozenset(
    {
        OrderStatus.VALIDATED,
        OrderStatus.ROUTED,
        OrderStatus.PARTIALLY_FILLED,
    }
)

TERMINAL_ORDER_STATUSES = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED,
    }
)


def ensure_transition_allowed(
    current_status: OrderStatus,
    target_status: OrderStatus,
) -> None:
    current = OrderStatus(current_status)
    target = OrderStatus(target_status)
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidStateTransition(current.value, target.value)
