from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.enums import BrokerEventType, OrderSide, OrderStatus, OrderType, TimeInForce
from app.models.account import Account
from app.models.fill import Fill
from app.models.order import Order
from app.models.position import Position
from app.repositories.account_repository import AccountRepository
from app.repositories.broker_event_repository import BrokerEventRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.position_repository import PositionRepository
from app.schemas.account import AccountCreate
from app.schemas.broker import BrokerExecutionEvent
from app.schemas.order import OrderCreate
from app.services.account_service import AccountService
from app.services.execution_service import ExecutionService
from app.services.order_lifecycle import OrderLifecycleService
from app.services.order_service import OrderService
from app.services.position_service import PositionService
from tests.support import RecordingBroker

pytestmark = pytest.mark.integration


def build_execution_service() -> ExecutionService:
    orders = OrderRepository()
    return ExecutionService(
        order_repository=orders,
        account_repository=AccountRepository(),
        broker_event_repository=BrokerEventRepository(),
        lifecycle=OrderLifecycleService(orders),
        position_service=PositionService(PositionRepository(), MarketDataRepository()),
    )


async def create_routed_order(
    session: AsyncSession,
    broker: RecordingBroker,
    *,
    quantity: Decimal = Decimal("100"),
    tif: TimeInForce = TimeInForce.GTC,
) -> tuple[Account, Order]:
    account = await AccountService(AccountRepository()).create_account(
        session,
        AccountCreate(
            user_id=f"user-{uuid4()}",
            initial_cash_balance=Decimal("100000"),
            currency="INR",
        ),
    )
    orders = OrderRepository()
    order = await OrderService(
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
            symbol="RELIANCE",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            time_in_force=tif,
            quantity=quantity,
            price=Decimal("100"),
        ),
    )
    return account, order


async def test_partial_fills_accumulate_and_update_cash_position(
    db_session: AsyncSession,
    recording_broker: RecordingBroker,
) -> None:
    account, order = await create_routed_order(db_session, recording_broker)
    service = build_execution_service()

    first = BrokerExecutionEvent(
        event_type=BrokerEventType.PARTIAL_FILL,
        order_id=order.id,
        filled_quantity=Decimal("40"),
        fill_price=Decimal("100"),
        execution_id="EXEC-1",
        timestamp=datetime.now(UTC),
    )
    second = BrokerExecutionEvent(
        event_type=BrokerEventType.FULL_FILL,
        order_id=order.id,
        filled_quantity=Decimal("60"),
        fill_price=Decimal("100"),
        execution_id="EXEC-2",
        timestamp=datetime.now(UTC),
    )

    assert await service.process_event(db_session, first) is True
    assert await service.process_event(db_session, second) is True
    assert await service.process_event(db_session, second) is False

    refreshed_order = await db_session.get(Order, order.id)
    await db_session.refresh(refreshed_order)
    assert refreshed_order.status == OrderStatus.FILLED
    assert refreshed_order.filled_quantity == Decimal("100.00000000")
    assert refreshed_order.remaining_quantity == Decimal("0E-8")
    assert refreshed_order.average_fill_price == Decimal("100.00000000")

    refreshed_account = await db_session.get(Account, account.id)
    await db_session.refresh(refreshed_account)
    assert refreshed_account.cash_balance == Decimal("90000.00000000")
    assert refreshed_account.reserved_cash == Decimal("0E-8")

    position = (
        await db_session.execute(
            select(Position).where(
                Position.account_id == account.id,
                Position.symbol == "RELIANCE",
            )
        )
    ).scalar_one()
    assert position.net_quantity == Decimal("100.00000000")
    assert position.average_entry_price == Decimal("100.00000000")

    fills = list(
        (
            await db_session.execute(
                select(Fill).where(Fill.order_id == order.id)
            )
        ).scalars()
    )
    assert len(fills) == 2


async def test_ioc_partial_fill_cancels_remainder_atomically(
    db_session: AsyncSession,
    recording_broker: RecordingBroker,
) -> None:
    account, order = await create_routed_order(
        db_session,
        recording_broker,
        tif=TimeInForce.IOC,
    )
    event = BrokerExecutionEvent(
        event_type=BrokerEventType.PARTIAL_FILL,
        order_id=order.id,
        filled_quantity=Decimal("30"),
        fill_price=Decimal("100"),
        execution_id="IOC-EXEC-1",
    )

    assert await build_execution_service().process_event(db_session, event) is True
    refreshed = await db_session.get(Order, order.id)
    await db_session.refresh(refreshed)
    assert refreshed.status == OrderStatus.CANCELLED
    assert refreshed.filled_quantity == Decimal("30.00000000")
    assert refreshed.cancelled_quantity == Decimal("70.00000000")
    assert refreshed.remaining_quantity == Decimal("0E-8")
