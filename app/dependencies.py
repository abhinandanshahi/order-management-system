from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.base import BrokerAdapter
from app.config import Settings, get_settings
from app.database import AsyncSessionFactory
from app.repositories.account_repository import AccountRepository
from app.repositories.broker_event_repository import BrokerEventRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.position_repository import PositionRepository
from app.services.account_service import AccountService
from app.services.cancellation_service import CancellationService
from app.services.execution_service import ExecutionService
from app.services.order_lifecycle import OrderLifecycleService
from app.services.order_service import OrderService
from app.services.pnl_service import PnLService
from app.services.position_service import PositionService


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        yield session


def get_broker_adapter(request: Request) -> BrokerAdapter:
    return request.app.state.broker_adapter


def get_order_repository() -> OrderRepository:
    return OrderRepository()


def get_account_repository() -> AccountRepository:
    return AccountRepository()


def get_position_repository() -> PositionRepository:
    return PositionRepository()


def get_order_service(
    orders: Annotated[OrderRepository, Depends(get_order_repository)],
    accounts: Annotated[AccountRepository, Depends(get_account_repository)],
    broker: Annotated[BrokerAdapter, Depends(get_broker_adapter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OrderService:
    lifecycle = OrderLifecycleService(orders)
    return OrderService(orders, accounts, lifecycle, broker, settings)


def get_account_service(
    accounts: Annotated[AccountRepository, Depends(get_account_repository)],
) -> AccountService:
    return AccountService(accounts)


def get_cancellation_service(
    orders: Annotated[OrderRepository, Depends(get_order_repository)],
    broker: Annotated[BrokerAdapter, Depends(get_broker_adapter)],
) -> CancellationService:
    return CancellationService(orders, OrderLifecycleService(orders), broker)


def get_execution_service(
    orders: Annotated[OrderRepository, Depends(get_order_repository)],
    accounts: Annotated[AccountRepository, Depends(get_account_repository)],
    positions: Annotated[PositionRepository, Depends(get_position_repository)],
) -> ExecutionService:
    return ExecutionService(
        order_repository=orders,
        account_repository=accounts,
        broker_event_repository=BrokerEventRepository(),
        lifecycle=OrderLifecycleService(orders),
        position_service=PositionService(positions, MarketDataRepository()),
    )


def get_pnl_service(
    positions: Annotated[PositionRepository, Depends(get_position_repository)],
) -> PnLService:
    return PnLService(positions)


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
