import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.broker.base import BrokerAdapter
from app.config import Settings
from app.repositories.account_repository import AccountRepository
from app.repositories.broker_event_repository import BrokerEventRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.position_repository import PositionRepository
from app.schemas.broker import BrokerExecutionEvent
from app.services.cancellation_service import CancellationService
from app.services.execution_service import ExecutionService
from app.services.order_lifecycle import OrderLifecycleService
from app.services.position_service import PositionService

logger = logging.getLogger(__name__)


def build_execution_service() -> ExecutionService:
    orders = OrderRepository()
    accounts = AccountRepository()
    positions = PositionRepository()
    lifecycle = OrderLifecycleService(orders)
    return ExecutionService(
        order_repository=orders,
        account_repository=accounts,
        broker_event_repository=BrokerEventRepository(),
        lifecycle=lifecycle,
        position_service=PositionService(positions, MarketDataRepository()),
    )


async def broker_event_worker(
    queue: asyncio.Queue[BrokerExecutionEvent],
    session_factory: async_sessionmaker[AsyncSession],
    service_factory: Callable[[], ExecutionService] = build_execution_service,
) -> None:
    while True:
        event = await queue.get()
        try:
            async with session_factory() as session:
                await service_factory().process_event(session, event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Broker event processing failed",
                extra={
                    "event_id": str(event.event_id),
                    "order_id": str(event.order_id),
                    "event_type": event.event_type.value,
                },
            )
        finally:
            queue.task_done()


async def day_order_expiry_worker(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    broker: BrokerAdapter,
    settings: Settings,
) -> None:
    orders = OrderRepository()
    lifecycle = OrderLifecycleService(orders)
    cancellation_service = CancellationService(orders, lifecycle, broker)

    while True:
        try:
            await asyncio.sleep(settings.day_order_scan_interval_seconds)
            async with session_factory() as session:
                async with session.begin():
                    from datetime import UTC, datetime

                    order_ids = await orders.list_expired_day_order_ids(
                        session,
                        datetime.now(UTC),
                    )

            for order_id in order_ids:
                try:
                    async with session_factory() as session:
                        await cancellation_service.request_cancellation(
                            session,
                            order_id,
                            reason="DAY order expired at session end",
                        )
                except Exception:
                    logger.exception(
                        "Failed to expire DAY order",
                        extra={"order_id": str(order_id)},
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("DAY order expiry worker failed")
