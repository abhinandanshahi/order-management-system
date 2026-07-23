from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.position_repository import PositionRepository
from app.schemas.position import PnLSummaryResponse


class PnLService:
    def __init__(self, position_repository: PositionRepository) -> None:
        self._positions = position_repository

    async def get_account_summary(
        self,
        session: AsyncSession,
        account_id: UUID,
    ) -> PnLSummaryResponse:
        positions = await self._positions.list_by_account(session, account_id)
        realized = sum(
            (position.realized_pnl for position in positions),
            start=Decimal("0"),
        )
        unrealized = sum(
            (position.unrealized_pnl for position in positions),
            start=Decimal("0"),
        )
        return PnLSummaryResponse(
            account_id=account_id,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            total_pnl=realized + unrealized,
        )
