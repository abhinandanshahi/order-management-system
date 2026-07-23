from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker_event import ProcessedBrokerEvent


class BrokerEventRepository:
    async def get_by_event_id(
        self,
        session: AsyncSession,
        event_id: UUID,
    ) -> ProcessedBrokerEvent | None:
        result = await session.execute(
            select(ProcessedBrokerEvent).where(
                ProcessedBrokerEvent.broker_event_id == event_id
            )
        )
        return result.scalar_one_or_none()

    async def add(
        self,
        session: AsyncSession,
        event: ProcessedBrokerEvent,
    ) -> ProcessedBrokerEvent:
        session.add(event)
        await session.flush()
        return event
