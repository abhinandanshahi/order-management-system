import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.base import BrokerAdapter
from app.config import Settings
from app.domain.enums import OrderEventType, OrderSide, OrderStatus, TimeInForce
from app.domain.exceptions import (
    AccountNotFound,
    BrokerUnavailable,
    DuplicateOrder,
    InsufficientBuyingPower,
    OrderNotFound,
)
from app.domain.order_rules import (
    ensure_sufficient_buying_power,
    required_buying_power,
)
from app.models.order import Order
from app.repositories.account_repository import AccountRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.broker import BrokerOrder
from app.schemas.order import OrderCreate
from app.services.order_lifecycle import OrderLifecycleService

logger = logging.getLogger(__name__)
ZERO = Decimal("0")


def order_matches_request(order: Order, payload: OrderCreate) -> bool:
    return all(
        (
            order.account_id == payload.account_id,
            order.client_order_id == payload.client_order_id,
            order.symbol == payload.symbol,
            order.side == payload.side,
            order.order_type == payload.order_type,
            order.time_in_force == payload.time_in_force,
            order.quantity == payload.quantity,
            order.price == payload.price,
        )
    )


class OrderService:
    def __init__(
        self,
        order_repository: OrderRepository,
        account_repository: AccountRepository,
        lifecycle: OrderLifecycleService,
        broker: BrokerAdapter,
        settings: Settings,
    ) -> None:
        self._orders = order_repository
        self._accounts = account_repository
        self._lifecycle = lifecycle
        self._broker = broker
        self._settings = settings

    async def create_order(
        self,
        session: AsyncSession,
        payload: OrderCreate,
    ) -> Order:
        should_route = False
        order: Order

        async with session.begin():
            account = await self._accounts.get_for_update(session, payload.account_id)
            if account is None:
                raise AccountNotFound(payload.account_id)

            existing_by_key = await self._orders.get_by_idempotency_key(
                session,
                payload.account_id,
                payload.idempotency_key,
            )
            if existing_by_key is not None:
                if not order_matches_request(existing_by_key, payload):
                    raise DuplicateOrder(payload.client_order_id)
                return existing_by_key

            existing_client_order = await self._orders.get_by_client_order_id(
                session,
                payload.account_id,
                payload.client_order_id,
            )
            if existing_client_order is not None:
                raise DuplicateOrder(payload.client_order_id)

            expires_at = None
            if payload.time_in_force == TimeInForce.DAY:
                expires_at = datetime.now(UTC) + timedelta(
                    seconds=self._settings.day_order_expiry_seconds
                )

            order = Order(
                client_order_id=payload.client_order_id,
                idempotency_key=payload.idempotency_key,
                account_id=payload.account_id,
                symbol=payload.symbol,
                side=payload.side,
                order_type=payload.order_type,
                time_in_force=payload.time_in_force,
                quantity=payload.quantity,
                price=payload.price,
                filled_quantity=ZERO,
                cancelled_quantity=ZERO,
                remaining_quantity=payload.quantity,
                status=OrderStatus.NEW,
                expires_at=expires_at,
            )
            await self._orders.add(session, order)
            await self._lifecycle.append_event(
                session,
                order,
                OrderEventType.ORDER_CREATED,
                new_status=OrderStatus.NEW,
                event_data={
                    "client_order_id": order.client_order_id,
                    "symbol": order.symbol,
                    "quantity": str(order.quantity),
                },
            )

            required_cash = required_buying_power(
                side=payload.side,
                quantity=payload.quantity,
                price=payload.price,
            )
            try:
                ensure_sufficient_buying_power(
                    available_cash=account.available_cash,
                    required_cash=required_cash,
                )
            except InsufficientBuyingPower as exc:
                order.rejection_reason = str(exc)
                await self._lifecycle.transition(
                    session,
                    order,
                    OrderStatus.REJECTED,
                    OrderEventType.VALIDATION_FAILED,
                    event_data={"reason": order.rejection_reason},
                )
                logger.info(
                    "Order rejected during validation",
                    extra={
                        "order_id": str(order.id),
                        "account_id": str(order.account_id),
                        "reason": order.rejection_reason,
                    },
                )
                return order

            await self._lifecycle.transition(
                session,
                order,
                OrderStatus.VALIDATED,
                OrderEventType.ORDER_VALIDATED,
            )

            if order.side == OrderSide.BUY:
                account.reserved_cash += required_cash
                account.version += 1

            await self._lifecycle.transition(
                session,
                order,
                OrderStatus.ROUTED,
                OrderEventType.ORDER_ROUTED,
            )
            should_route = True

        if should_route:
            try:
                await self._broker.submit_order(
                    BrokerOrder(
                        order_id=order.id,
                        symbol=order.symbol,
                        side=order.side,
                        time_in_force=order.time_in_force,
                        quantity=order.quantity,
                        remaining_quantity=order.remaining_quantity,
                        price=order.price,
                    )
                )
            except Exception as exc:
                logger.exception(
                    "Failed to submit order to broker",
                    extra={"order_id": str(order.id)},
                )
                await self._mark_routing_failure(session, order.id, str(exc))
                raise BrokerUnavailable() from exc

        logger.info(
            "Order created",
            extra={
                "order_id": str(order.id),
                "account_id": str(order.account_id),
                "status": order.status,
            },
        )
        return order

    async def _mark_routing_failure(
        self,
        session: AsyncSession,
        order_id: UUID,
        reason: str,
    ) -> None:
        async with session.begin():
            order = await self._orders.get_for_update(session, order_id)
            if order is None or order.status != OrderStatus.ROUTED:
                return

            account = await self._accounts.get_for_update(session, order.account_id)
            if account is None:
                raise AccountNotFound(order.account_id)

            if order.side == OrderSide.BUY:
                account.reserved_cash -= order.remaining_quantity * order.price
                account.version += 1

            order.rejection_reason = f"Broker routing failed: {reason}"
            await self._lifecycle.transition(
                session,
                order,
                OrderStatus.REJECTED,
                OrderEventType.ORDER_REJECTED,
                event_data={"reason": order.rejection_reason},
            )

    async def get_order(
        self,
        session: AsyncSession,
        order_id: UUID,
    ) -> Order:
        order = await self._orders.get_by_id(session, order_id)
        if order is None:
            raise OrderNotFound(order_id)
        return order

    async def list_orders(
        self,
        session: AsyncSession,
        *,
        account_id: UUID | None,
        status: OrderStatus | None,
        open_only: bool,
        limit: int,
        offset: int,
    ) -> list[Order]:
        return await self._orders.list_orders(
            session,
            account_id=account_id,
            status=status,
            open_only=open_only,
            limit=limit,
            offset=offset,
        )
