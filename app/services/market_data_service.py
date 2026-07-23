from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.position_repository import PositionRepository
from app.services.position_service import calculate_unrealized_pnl


class MarketDataService:
    def __init__(
        self,
        market_data_repository: MarketDataRepository,
        position_repository: PositionRepository,
    ) -> None:
        self._market_data = market_data_repository
        self._positions = position_repository

    async def apply_tick(
        self,
        session: AsyncSession,
        *,
        symbol: str,
        price: Decimal,
        observed_at: datetime,
    ) -> None:
        normalized_symbol = symbol.upper()
        async with session.begin():
            _, applied = await self._market_data.upsert(
                session,
                symbol=normalized_symbol,
                price=price,
                observed_at=observed_at,
            )
            if not applied:
                return

            positions = await self._positions.list_by_symbol_for_update(
                session,
                normalized_symbol,
            )
            for position in positions:
                position.last_mark_price = price
                position.unrealized_pnl = calculate_unrealized_pnl(
                    net_quantity=position.net_quantity,
                    average_entry_price=position.average_entry_price,
                    mark_price=price,
                )
