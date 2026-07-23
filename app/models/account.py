from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("cash_balance >= 0", name="ck_accounts_cash_nonnegative"),
        CheckConstraint("reserved_cash >= 0", name="ck_accounts_reserved_nonnegative"),
        CheckConstraint(
            "reserved_cash <= cash_balance",
            name="ck_accounts_reserved_not_above_cash",
        ),
        Index("ix_accounts_user_id", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    cash_balance: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("0")
    )
    reserved_cash: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("0")
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    orders = relationship("Order", back_populates="account")
    positions = relationship("Position", back_populates="account")

    @property
    def available_cash(self) -> Decimal:
        return self.cash_balance - self.reserved_cash
