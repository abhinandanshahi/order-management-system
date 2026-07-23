from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Position(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("account_id", "symbol", name="uq_positions_account_symbol"),
        CheckConstraint(
            "average_entry_price >= 0",
            name="ck_positions_average_price_nonnegative",
        ),
        CheckConstraint(
            "last_mark_price IS NULL OR last_mark_price > 0",
            name="ck_positions_mark_price_positive",
        ),
        Index("ix_positions_symbol", "symbol"),
    )

    account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    net_quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("0")
    )
    average_entry_price: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("0")
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("0")
    )
    unrealized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("0")
    )
    last_mark_price: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 8), nullable=True
    )

    account = relationship("Account", back_populates="positions")
