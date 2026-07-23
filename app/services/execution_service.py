import logging
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    BrokerEventType,
    OrderEventType,
    OrderSide,
    OrderStatus,
    TimeInForce,
)
from app.domain.exceptions import AccountNotFound, InvalidFill, OrderNotFound
from app.models.broker_event import ProcessedBrokerEvent
from app.models.fill import Fill
from app.models.order import Order
from app.repositories.account_repository import AccountRepository
from app.repositories.broker_event_repository import BrokerEventRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.broker import BrokerExecutionEvent
from app.services.order_lifecycle import OrderLifecycleService
from app.services.position_service import PositionService

logger = logging.getLogger(__name__)
ZERO = Decimal("0")


class ExecutionService:
    def __init__(
        self,
        order_repository: OrderRepository,
        account_repository: AccountRepository,
        broker_event_repository: BrokerEventRepository,
        lifecycle: OrderLifecycleService,
        position_service: PositionService,
    ) -> None:
        self._orders = order_repository
        self._accounts = account_repository
        self._broker_events = broker_event_repository
        self._lifecycle = lifecycle
        self._positions = position_service

    async def process_event(
        self,
        session: AsyncSession,
        event: BrokerExecutionEvent,
    ) -> bool:
        async with session.begin():
            order = await self._orders.get_for_update(session, event.order_id)
            if order is None:
                raise OrderNotFound(event.order_id)

            processed = await self._broker_events.get_by_event_id(
                session,
                event.event_id,
            )
            if processed is not None:
                logger.info(
                    "Duplicate broker event ignored",
                    extra={
                        "event_id": str(event.event_id),
                        "order_id": str(event.order_id),
                    },
                )
                return False

            applied, reason = await self._dispatch(session, order, event)
            await self._broker_events.add(
                session,
                ProcessedBrokerEvent(
                    broker_event_id=event.event_id,
                    order_id=event.order_id,
                    event_type=event.event_type,
                    broker_timestamp=event.timestamp,
                    outcome="APPLIED" if applied else "IGNORED",
                    details={"reason": reason} if reason else {},
                ),
            )

            if not applied:
                await self._lifecycle.append_event(
                    session,
                    order,
                    OrderEventType.BROKER_EVENT_IGNORED,
                    previous_status=order.status,
                    new_status=order.status,
                    event_data={
                        "broker_event_id": str(event.event_id),
                        "event_type": event.event_type.value,
                        "reason": reason,
                    },
                )

        logger.info(
            "Broker event processed",
            extra={
                "event_id": str(event.event_id),
                "order_id": str(event.order_id),
                "event_type": event.event_type.value,
                "applied": applied,
            },
        )
        return applied

    async def _dispatch(
        self,
        session: AsyncSession,
        order: Order,
        event: BrokerExecutionEvent,
    ) -> tuple[bool, str | None]:
        if event.event_type in {
            BrokerEventType.FULL_FILL,
            BrokerEventType.PARTIAL_FILL,
        }:
            return await self._apply_fill(session, order, event)
        if event.event_type == BrokerEventType.REJECTED:
            return await self._apply_rejection(session, order, event)
        if event.event_type == BrokerEventType.CANCELLED:
            return await self._apply_cancellation(session, order, event)
        return False, "Unsupported broker event"

    async def _apply_fill(
        self,
        session: AsyncSession,
        order: Order,
        event: BrokerExecutionEvent,
    ) -> tuple[bool, str | None]:
        if order.status not in {
            OrderStatus.ROUTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
        }:
            return False, f"Order is already {order.status}"

        fill_quantity = event.filled_quantity
        fill_price = event.fill_price
        if fill_price is None:
            raise InvalidFill("Fill price is required")
        if fill_quantity <= ZERO:
            raise InvalidFill("Fill quantity must be positive")
        if fill_quantity > order.remaining_quantity:
            return False, "Fill quantity exceeds remaining quantity"
        if (
            event.event_type == BrokerEventType.FULL_FILL
            and fill_quantity != order.remaining_quantity
        ):
            return False, "Full-fill event does not consume remaining quantity"

        previous_filled = order.filled_quantity
        new_filled = previous_filled + fill_quantity
        previous_value = previous_filled * (order.average_fill_price or ZERO)
        order.average_fill_price = (
            previous_value + fill_quantity * fill_price
        ) / new_filled
        order.filled_quantity = new_filled
        order.remaining_quantity -= fill_quantity
        order.version += 1

        await self._orders.add_fill(
            session,
            Fill(
                order_id=order.id,
                broker_event_id=event.event_id,
                execution_id=event.execution_id or str(event.event_id),
                quantity=fill_quantity,
                price=fill_price,
                executed_at=event.timestamp,
            ),
        )

        account = await self._accounts.get_for_update(session, order.account_id)
        if account is None:
            raise AccountNotFound(order.account_id)

        notional = fill_quantity * fill_price
        if order.side == OrderSide.BUY:
            reserved_release = fill_quantity * order.price
            if reserved_release > account.reserved_cash:
                raise InvalidFill("Reserved cash is inconsistent with the order")
            if notional > account.cash_balance:
                raise InvalidFill("Fill would create a negative cash balance")
            account.reserved_cash -= reserved_release
            account.cash_balance -= notional
        else:
            account.cash_balance += notional
        account.version += 1

        await self._positions.apply_execution(
            session,
            account_id=order.account_id,
            symbol=order.symbol,
            side=order.side,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
        )

        event_data = {
            "broker_event_id": str(event.event_id),
            "execution_id": event.execution_id,
            "quantity": str(fill_quantity),
            "price": str(fill_price),
        }

        if order.remaining_quantity == ZERO:
            await self._lifecycle.transition(
                session,
                order,
                OrderStatus.FILLED,
                OrderEventType.FULL_FILL_RECEIVED,
                event_data=event_data,
            )
            return True, None

        if order.time_in_force == TimeInForce.IOC:
            await self._lifecycle.append_event(
                session,
                order,
                OrderEventType.PARTIAL_FILL_RECEIVED,
                previous_status=order.status,
                new_status=order.status,
                event_data=event_data,
            )
            await self._cancel_remaining(
                session,
                order,
                reason="IOC remainder cancelled",
                event_data=event_data,
            )
            return True, None

        if order.status == OrderStatus.ROUTED:
            await self._lifecycle.transition(
                session,
                order,
                OrderStatus.PARTIALLY_FILLED,
                OrderEventType.PARTIAL_FILL_RECEIVED,
                event_data=event_data,
            )
        else:
            await self._lifecycle.append_event(
                session,
                order,
                OrderEventType.PARTIAL_FILL_RECEIVED,
                previous_status=order.status,
                new_status=order.status,
                event_data=event_data,
            )
        return True, None

    async def _apply_rejection(
        self,
        session: AsyncSession,
        order: Order,
        event: BrokerExecutionEvent,
    ) -> tuple[bool, str | None]:
        if order.status != OrderStatus.ROUTED:
            return False, f"Order cannot be rejected from {order.status}"

        account = await self._accounts.get_for_update(session, order.account_id)
        if account is None:
            raise AccountNotFound(order.account_id)
        self._release_remaining_reservation(account, order)

        order.rejection_reason = event.reason or "Rejected by broker"
        await self._lifecycle.transition(
            session,
            order,
            OrderStatus.REJECTED,
            OrderEventType.ORDER_REJECTED,
            event_data={
                "broker_event_id": str(event.event_id),
                "reason": order.rejection_reason,
            },
        )
        return True, None

    async def _apply_cancellation(
        self,
        session: AsyncSession,
        order: Order,
        event: BrokerExecutionEvent,
    ) -> tuple[bool, str | None]:
        if order.status not in {
            OrderStatus.ROUTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
        }:
            return False, f"Order cannot be cancelled from {order.status}"

        await self._cancel_remaining(
            session,
            order,
            reason=event.reason or "Cancelled by broker",
            event_data={"broker_event_id": str(event.event_id)},
        )
        return True, None

    async def _cancel_remaining(
        self,
        session: AsyncSession,
        order: Order,
        *,
        reason: str,
        event_data: dict,
    ) -> None:
        account = await self._accounts.get_for_update(session, order.account_id)
        if account is None:
            raise AccountNotFound(order.account_id)

        self._release_remaining_reservation(account, order)
        cancelled = order.remaining_quantity
        order.cancelled_quantity += cancelled
        order.remaining_quantity = ZERO
        order.version += 1

        await self._lifecycle.transition(
            session,
            order,
            OrderStatus.CANCELLED,
            OrderEventType.ORDER_CANCELLED,
            event_data={
                **event_data,
                "cancelled_quantity": str(cancelled),
                "reason": reason,
            },
        )

    @staticmethod
    def _release_remaining_reservation(account, order: Order) -> None:
        if order.side != OrderSide.BUY or order.remaining_quantity <= ZERO:
            return
        release_amount = order.remaining_quantity * order.price
        if release_amount > account.reserved_cash:
            raise InvalidFill("Reserved cash is inconsistent with the order")
        account.reserved_cash -= release_amount
        account.version += 1
