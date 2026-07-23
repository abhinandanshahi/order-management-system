import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.base import BrokerAdapter
from app.domain.enums import OrderEventType, OrderStatus
from app.domain.exceptions import InvalidCancellation, OrderNotFound
from app.domain.order_state_machine import CANCELLABLE_ORDER_STATUSES
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.services.order_lifecycle import OrderLifecycleService

logger = logging.getLogger(__name__)


class CancellationService:
    def __init__(
        self,
        order_repository: OrderRepository,
        lifecycle: OrderLifecycleService,
        broker: BrokerAdapter,
    ) -> None:
        self._orders = order_repository
        self._lifecycle = lifecycle
        self._broker = broker

    async def request_cancellation(
        self,
        session: AsyncSession,
        order_id: UUID,
        *,
        reason: str = "Client requested cancellation",
    ) -> Order:
        should_notify_broker = False

        async with session.begin():
            order = await self._orders.get_for_update(session, order_id)
            if order is None:
                raise OrderNotFound(order_id)

            if order.status == OrderStatus.CANCEL_PENDING:
                return order
            if order.status not in CANCELLABLE_ORDER_STATUSES:
                raise InvalidCancellation(
                    f"Order cannot be cancelled from {order.status}"
                )

            await self._lifecycle.transition(
                session,
                order,
                OrderStatus.CANCEL_PENDING,
                OrderEventType.CANCEL_REQUESTED,
                event_data={"reason": reason},
            )
            should_notify_broker = True

        if should_notify_broker:
            await self._broker.cancel_order(order.id, reason=reason)
            logger.info(
                "Order cancellation requested",
                extra={"order_id": str(order.id), "reason": reason},
            )
        return order
