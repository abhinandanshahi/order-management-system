from uuid import UUID

from app.broker.base import BrokerAdapter
from app.schemas.broker import BrokerOrder


class RecordingBroker(BrokerAdapter):
    def __init__(self) -> None:
        self.submitted_orders: list[BrokerOrder] = []
        self.cancelled_orders: list[tuple[UUID, str]] = []

    async def submit_order(self, order: BrokerOrder) -> None:
        self.submitted_orders.append(order)

    async def cancel_order(self, order_id: UUID, *, reason: str) -> None:
        self.cancelled_orders.append((order_id, reason))
