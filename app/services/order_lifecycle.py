from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OrderEventType, OrderStatus
from app.domain.order_state_machine import ensure_transition_allowed
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.repositories.order_repository import OrderRepository


class OrderLifecycleService:
    def __init__(self, order_repository: OrderRepository) -> None:
        self._orders = order_repository

    async def append_event(
        self,
        session: AsyncSession,
        order: Order,
        event_type: OrderEventType,
        *,
        previous_status: OrderStatus | None = None,
        new_status: OrderStatus | None = None,
        event_data: dict[str, Any] | None = None,
    ) -> OrderEvent:
        return await self._orders.add_event(
            session,
            OrderEvent(
                order_id=order.id,
                event_type=event_type,
                previous_status=previous_status,
                new_status=new_status,
                event_data=event_data or {},
            ),
        )

    async def transition(
        self,
        session: AsyncSession,
        order: Order,
        target_status: OrderStatus,
        event_type: OrderEventType,
        *,
        event_data: dict[str, Any] | None = None,
    ) -> None:
        previous_status = order.status
        ensure_transition_allowed(previous_status, target_status)
        order.status = target_status
        order.version += 1

        await self.append_event(
            session,
            order,
            event_type,
            previous_status=previous_status,
            new_status=target_status,
            event_data=event_data,
        )
