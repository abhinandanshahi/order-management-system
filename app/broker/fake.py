import asyncio
import logging
import random
from decimal import ROUND_DOWN, Decimal
from uuid import UUID, uuid4

from app.broker.base import BrokerAdapter
from app.config import Settings
from app.domain.enums import BrokerEventType, TimeInForce
from app.schemas.broker import BrokerExecutionEvent, BrokerOrder

logger = logging.getLogger(__name__)
QUANTITY_STEP = Decimal("0.00000001")


class FakeBrokerAdapter(BrokerAdapter):
    """Seeded asynchronous broker simulator used by the assignment."""

    def __init__(
        self,
        event_queue: asyncio.Queue[BrokerExecutionEvent],
        settings: Settings,
    ) -> None:
        self._queue = event_queue
        self._settings = settings
        self._random = random.Random(settings.broker_random_seed)
        self._tasks: set[asyncio.Task[None]] = set()

    async def submit_order(self, order: BrokerOrder) -> None:
        self._start_task(self._simulate_order(order))

    async def cancel_order(self, order_id: UUID, *, reason: str) -> None:
        self._start_task(self._simulate_cancellation(order_id, reason))

    def _start_task(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        exception = task.exception()
        if exception is not None:
            logger.error(
                "Fake broker task failed",
                exc_info=(type(exception), exception, exception.__traceback__),
            )

    async def _sleep(self) -> None:
        delay = self._random.uniform(
            self._settings.broker_min_delay_seconds,
            self._settings.broker_max_delay_seconds,
        )
        await asyncio.sleep(delay)

    async def _simulate_order(self, order: BrokerOrder) -> None:
        await self._sleep()
        outcome = self._random.choices(
            population=("FULL_FILL", "PARTIAL_FILL", "REJECTED"),
            weights=(50, 35, 15),
            k=1,
        )[0]

        if outcome == "REJECTED":
            await self._queue.put(
                BrokerExecutionEvent(
                    event_type=BrokerEventType.REJECTED,
                    order_id=order.order_id,
                    reason="Rejected by simulated broker",
                )
            )
            return

        if outcome == "FULL_FILL":
            await self._queue.put(self._full_fill_event(order, order.remaining_quantity))
            return

        partial_quantity = self._partial_quantity(order.remaining_quantity)
        await self._queue.put(
            BrokerExecutionEvent(
                event_type=BrokerEventType.PARTIAL_FILL,
                order_id=order.order_id,
                filled_quantity=partial_quantity,
                fill_price=order.price,
                execution_id=f"SIM-{uuid4()}",
            )
        )

        if order.time_in_force == TimeInForce.IOC:
            return

        remaining = order.remaining_quantity - partial_quantity
        if remaining > 0 and self._random.random() < 0.65:
            await self._sleep()
            await self._queue.put(self._full_fill_event(order, remaining))

    def _full_fill_event(
        self,
        order: BrokerOrder,
        quantity: Decimal,
    ) -> BrokerExecutionEvent:
        return BrokerExecutionEvent(
            event_type=BrokerEventType.FULL_FILL,
            order_id=order.order_id,
            filled_quantity=quantity,
            fill_price=order.price,
            execution_id=f"SIM-{uuid4()}",
        )

    def _partial_quantity(self, remaining: Decimal) -> Decimal:
        ratio = Decimal(str(self._random.uniform(0.25, 0.75)))
        quantity = (remaining * ratio).quantize(QUANTITY_STEP, rounding=ROUND_DOWN)
        if quantity <= 0:
            return remaining
        if quantity >= remaining:
            return max(remaining - QUANTITY_STEP, QUANTITY_STEP)
        return quantity

    async def _simulate_cancellation(self, order_id: UUID, reason: str) -> None:
        await self._sleep()
        await self._queue.put(
            BrokerExecutionEvent(
                event_type=BrokerEventType.CANCELLED,
                order_id=order_id,
                reason=reason,
            )
        )

    async def close(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
