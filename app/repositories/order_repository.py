from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import OrderStatus, TimeInForce
from app.domain.order_state_machine import OPEN_ORDER_STATUSES
from app.models.fill import Fill
from app.models.order import Order
from app.models.order_event import OrderEvent


class OrderRepository:
    async def add(self, session: AsyncSession, order: Order) -> Order:
        session.add(order)
        await session.flush()
        return order

    async def get_by_id(
        self,
        session: AsyncSession,
        order_id: UUID,
    ) -> Order | None:
        return await session.get(Order, order_id)

    async def get_for_update(
        self,
        session: AsyncSession,
        order_id: UUID,
    ) -> Order | None:
        result = await session.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(
        self,
        session: AsyncSession,
        account_id: UUID,
        idempotency_key: str,
    ) -> Order | None:
        result = await session.execute(
            select(Order).where(
                Order.account_id == account_id,
                Order.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_client_order_id(
        self,
        session: AsyncSession,
        account_id: UUID,
        client_order_id: str,
    ) -> Order | None:
        result = await session.execute(
            select(Order).where(
                Order.account_id == account_id,
                Order.client_order_id == client_order_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_orders(
        self,
        session: AsyncSession,
        *,
        account_id: UUID | None = None,
        status: OrderStatus | None = None,
        open_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Order]:
        statement: Select[tuple[Order]] = select(Order)
        if account_id is not None:
            statement = statement.where(Order.account_id == account_id)
        if status is not None:
            statement = statement.where(Order.status == status)
        if open_only:
            statement = statement.where(Order.status.in_(OPEN_ORDER_STATUSES))

        result = await session.execute(
            statement.order_by(Order.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def list_expired_day_order_ids(
        self,
        session: AsyncSession,
        now: datetime,
        limit: int = 100,
    ) -> list[UUID]:
        result = await session.execute(
            select(Order.id)
            .where(
                Order.time_in_force == TimeInForce.DAY,
                Order.status.in_(OPEN_ORDER_STATUSES),
                Order.expires_at.is_not(None),
                Order.expires_at <= now,
            )
            .order_by(Order.expires_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_event(
        self,
        session: AsyncSession,
        event: OrderEvent,
    ) -> OrderEvent:
        session.add(event)
        await session.flush()
        return event

    async def add_fill(
        self,
        session: AsyncSession,
        fill: Fill,
    ) -> Fill:
        session.add(fill)
        await session.flush()
        return fill

    async def list_fills(
        self,
        session: AsyncSession,
        order_id: UUID,
    ) -> list[Fill]:
        result = await session.execute(
            select(Fill)
            .where(Fill.order_id == order_id)
            .order_by(Fill.executed_at)
        )
        return list(result.scalars().all())

    async def list_events(
        self,
        session: AsyncSession,
        order_id: UUID,
    ) -> list[OrderEvent]:
        result = await session.execute(
            select(OrderEvent)
            .where(OrderEvent.order_id == order_id)
            .order_by(OrderEvent.created_at)
        )
        return list(result.scalars().all())

    async def get_with_history(
        self,
        session: AsyncSession,
        order_id: UUID,
    ) -> Order | None:
        result = await session.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.events), selectinload(Order.fills))
        )
        return result.scalar_one_or_none()
