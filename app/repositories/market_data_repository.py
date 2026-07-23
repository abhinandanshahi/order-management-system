from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_price import MarketPrice


class MarketDataRepository:
    async def get(
        self,
        session: AsyncSession,
        symbol: str,
    ) -> MarketPrice | None:
        return await session.get(MarketPrice, symbol)

    async def upsert(
        self,
        session: AsyncSession,
        *,
        symbol: str,
        price: Decimal,
        observed_at: datetime,
    ) -> tuple[MarketPrice, bool]:
        market_price = await self.get(session, symbol)
        applied = False
        if market_price is None:
            market_price = MarketPrice(
                symbol=symbol,
                price=price,
                observed_at=observed_at,
            )
            session.add(market_price)
            applied = True
        elif observed_at >= market_price.observed_at:
            market_price.price = price
            market_price.observed_at = observed_at
            applied = True

        await session.flush()
        return market_price, applied
