from abc import ABC, abstractmethod
from uuid import UUID

from app.schemas.broker import BrokerOrder


class BrokerAdapter(ABC):
    @abstractmethod
    async def submit_order(self, order: BrokerOrder) -> None:
        """Submit an order without waiting for its execution outcome."""

    @abstractmethod
    async def cancel_order(self, order_id: UUID, *, reason: str) -> None:
        """Request cancellation without waiting for broker acknowledgement."""

    async def close(self) -> None:
        """Release adapter resources during application shutdown."""
        return None
