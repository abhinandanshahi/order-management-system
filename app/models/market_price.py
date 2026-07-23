from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class MarketPrice(TimestampMixin, Base):
    __tablename__ = "market_prices"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_market_prices_price_positive"),
    )

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
