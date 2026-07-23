from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Fill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fills"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_fills_quantity_positive"),
        CheckConstraint("price > 0", name="ck_fills_price_positive"),
        Index("ix_fills_order_id", "order_id"),
    )

    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    broker_event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, unique=True
    )
    execution_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    order = relationship("Order", back_populates="fills")
