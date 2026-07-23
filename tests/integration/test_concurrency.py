import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.database import AsyncSessionFactory
from app.domain.enums import BrokerEventType, OrderSide, OrderStatus, OrderType, TimeInForce
from app.models.fill import Fill
from app.models.order import Order
from app.repositories.account_repository import AccountRepository
from app.repositories.broker_event_repository import BrokerEventRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.position_repository import PositionRepository
from app.schemas.account import AccountCreate
from app.schemas.broker import BrokerExecutionEvent
from app.schemas.order import OrderCreate
from app.services.account_service import AccountService
from app.services.cancellation_service import CancellationService
from app.services.execution_service import ExecutionService
from app.services.order_lifecycle import OrderLifecycleService
from app.services.order_service import OrderService
from app.services.position_service import PositionService
from tests.support import RecordingBroker

pytestmark = [pytest.mark.integration, pytest.mark.concurrency]


def execution_service() -> ExecutionService:
    orders = OrderRepository()
    return ExecutionService(
        order_repository=orders,
        account_repository=AccountRepository(),
        broker_event_repository=BrokerEventRepository(),
        lifecycle=OrderLifecycleService(orders),
        position_service=PositionService(PositionRepository(), MarketDataRepository()),
    )


async def create_order(broker: RecordingBroker) -> Order:
    async with AsyncSessionFactory() as session:
        account = await AccountService(AccountRepository()).create_account(
            session,
            AccountCreate(
                user_id=f"user-{uuid4()}",
                initial_cash_balance=Decimal("100000"),
            ),
        )
        orders = OrderRepository()
        return await OrderService(
            orders,
            AccountRepository(),
            OrderLifecycleService(orders),
            broker,
            get_settings(),
        ).create_order(
            session,
            OrderCreate(
                client_order_id=f"client-{uuid4()}",
                idempotency_key=f"idem-{uuid4()}",
                account_id=account.id,
                symbol="NIFTY",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                time_in_force=TimeInForce.GTC,
                quantity=Decimal("100"),
                price=Decimal("100"),
            ),
        )


async def process_in_new_session(event: BrokerExecutionEvent) -> bool:
    async with AsyncSessionFactory() as session:
        return await execution_service().process_event(session, event)


async def test_simultaneous_fills_do_not_lose_updates(
    recording_broker: RecordingBroker,
) -> None:
    order = await create_order(recording_broker)
    events = [
        BrokerExecutionEvent(
            event_type=BrokerEventType.PARTIAL_FILL,
            order_id=order.id,
            filled_quantity=Decimal("50"),
            fill_price=Decimal("100"),
            execution_id="CONCURRENT-1",
        ),
        BrokerExecutionEvent(
            event_type=BrokerEventType.PARTIAL_FILL,
            order_id=order.id,
            filled_quantity=Decimal("50"),
            fill_price=Decimal("100"),
            execution_id="CONCURRENT-2",
        ),
    ]

    results = await asyncio.gather(*(process_in_new_session(event) for event in events))
    assert results == [True, True]

    async with AsyncSessionFactory() as session:
        persisted = await session.get(Order, order.id)
        assert persisted.status == OrderStatus.FILLED
        assert persisted.filled_quantity == Decimal("100.00000000")
        assert persisted.remaining_quantity == Decimal("0E-8")


async def test_duplicate_broker_event_is_applied_once(
    recording_broker: RecordingBroker,
) -> None:
    order = await create_order(recording_broker)
    event = BrokerExecutionEvent(
        event_type=BrokerEventType.PARTIAL_FILL,
        order_id=order.id,
        filled_quantity=Decimal("25"),
        fill_price=Decimal("100"),
        execution_id="DUPLICATE-EXEC",
    )

    results = await asyncio.gather(
        process_in_new_session(event),
        process_in_new_session(event),
    )
    assert sorted(results) == [False, True]

    async with AsyncSessionFactory() as session:
        fill_count = await session.scalar(
            select(func.count()).select_from(Fill).where(Fill.order_id == order.id)
        )
        persisted = await session.get(Order, order.id)
        assert fill_count == 1
        assert persisted.filled_quantity == Decimal("25.00000000")


async def test_concurrent_cancellation_requests_are_idempotent(
    recording_broker: RecordingBroker,
) -> None:
    order = await create_order(recording_broker)

    async def cancel() -> OrderStatus:
        async with AsyncSessionFactory() as session:
            orders = OrderRepository()
            result = await CancellationService(
                orders,
                OrderLifecycleService(orders),
                recording_broker,
            ).request_cancellation(session, order.id)
            return result.status

    statuses = await asyncio.gather(cancel(), cancel())
    assert statuses == [OrderStatus.CANCEL_PENDING, OrderStatus.CANCEL_PENDING]
    assert len(recording_broker.cancelled_orders) == 1


async def test_simultaneous_duplicate_submissions_return_one_order(
    recording_broker: RecordingBroker,
) -> None:
    async with AsyncSessionFactory() as session:
        account = await AccountService(AccountRepository()).create_account(
            session,
            AccountCreate(
                user_id=f"user-{uuid4()}",
                initial_cash_balance=Decimal("100000"),
            ),
        )

    payload = OrderCreate(
        client_order_id="same-client-order",
        idempotency_key="same-idempotency-key",
        account_id=account.id,
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        time_in_force=TimeInForce.GTC,
        quantity=Decimal("10"),
        price=Decimal("100"),
    )

    async def submit() -> Order:
        async with AsyncSessionFactory() as session:
            orders = OrderRepository()
            return await OrderService(
                orders,
                AccountRepository(),
                OrderLifecycleService(orders),
                recording_broker,
                get_settings(),
            ).create_order(session, payload)

    first, second = await asyncio.gather(submit(), submit())
    assert first.id == second.id
    assert len(recording_broker.submitted_orders) == 1

    async with AsyncSessionFactory() as session:
        order_count = await session.scalar(select(func.count()).select_from(Order))
        assert order_count == 1
