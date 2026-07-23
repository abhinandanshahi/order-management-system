from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OrderSide
from app.domain.position_rules import (
    ZERO,
    calculate_position_after_fill,
    calculate_unrealized_pnl,
)
from app.models.position import Position
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.position_repository import PositionRepository


class PositionService:
    def __init__(
        self,
        repository: PositionRepository,
        market_data_repository: MarketDataRepository,
    ) -> None:
        self._positions = repository
        self._market_data = market_data_repository

    async def apply_execution(
        self,
        session: AsyncSession,
        *,
        account_id: UUID,
        symbol: str,
        side: OrderSide,
        fill_quantity: Decimal,
        fill_price: Decimal,
    ) -> Position:
        position = await self._positions.get_for_update(session, account_id, symbol)
        market_price = await self._market_data.get(session, symbol)
        mark_price = market_price.price if market_price is not None else fill_price
        if position is None:
            position = Position(
                account_id=account_id,
                symbol=symbol,
                net_quantity=ZERO,
                average_entry_price=ZERO,
                realized_pnl=ZERO,
                unrealized_pnl=ZERO,
                last_mark_price=mark_price,
            )
            await self._positions.add(session, position)

        result = calculate_position_after_fill(
            current_quantity=position.net_quantity,
            current_average_price=position.average_entry_price,
            current_realized_pnl=position.realized_pnl,
            side=side,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
        )
        position.net_quantity = result.net_quantity
        position.average_entry_price = result.average_entry_price
        position.realized_pnl = result.realized_pnl
        position.last_mark_price = mark_price
        position.unrealized_pnl = calculate_unrealized_pnl(
            net_quantity=position.net_quantity,
            average_entry_price=position.average_entry_price,
            mark_price=position.last_mark_price,
        )
        return position
