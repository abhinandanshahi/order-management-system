from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position import Position


class PositionRepository:
    async def add(self, session: AsyncSession, position: Position) -> Position:
        session.add(position)
        await session.flush()
        return position

    async def get_for_update(
        self,
        session: AsyncSession,
        account_id: UUID,
        symbol: str,
    ) -> Position | None:
        result = await session.execute(
            select(Position)
            .where(
                Position.account_id == account_id,
                Position.symbol == symbol,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_by_account(
        self,
        session: AsyncSession,
        account_id: UUID,
    ) -> list[Position]:
        result = await session.execute(
            select(Position)
            .where(Position.account_id == account_id)
            .order_by(Position.symbol)
        )
        return list(result.scalars().all())

    async def list_by_symbol_for_update(
        self,
        session: AsyncSession,
        symbol: str,
    ) -> list[Position]:
        result = await session.execute(
            select(Position)
            .where(Position.symbol == symbol)
            .with_for_update()
        )
        return list(result.scalars().all())
