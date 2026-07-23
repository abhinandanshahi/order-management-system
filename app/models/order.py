from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "client_order_id",
            name="uq_orders_account_client_order",
        ),
        UniqueConstraint(
            "account_id",
            "idempotency_key",
            name="uq_orders_account_idempotency_key",
        ),
        CheckConstraint("quantity > 0", name="ck_orders_quantity_positive"),
        CheckConstraint("price > 0", name="ck_orders_price_positive"),
        CheckConstraint("filled_quantity >= 0", name="ck_orders_filled_nonnegative"),
        CheckConstraint(
            "cancelled_quantity >= 0",
            name="ck_orders_cancelled_nonnegative",
        ),
        CheckConstraint(
            "remaining_quantity >= 0",
            name="ck_orders_remaining_nonnegative",
        ),
        CheckConstraint(
            "filled_quantity + cancelled_quantity + remaining_quantity = quantity",
            name="ck_orders_quantity_conservation",
        ),
        CheckConstraint("side IN ('BUY', 'SELL')", name="ck_orders_side"),
        CheckConstraint(
            "order_type IN ('MARKET', 'LIMIT')",
            name="ck_orders_type",
        ),
        CheckConstraint(
            "time_in_force IN ('DAY', 'GTC', 'IOC')",
            name="ck_orders_tif",
        ),
        CheckConstraint(
            "status IN ('NEW','VALIDATED','ROUTED','PARTIALLY_FILLED','FILLED',"
            "'REJECTED','CANCEL_PENDING','CANCELLED')",
            name="ck_orders_status",
        ),
        Index("ix_orders_account_status", "account_id", "status"),
        Index("ix_orders_symbol", "symbol"),
        Index("ix_orders_expires_at", "expires_at"),
    )

    client_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[OrderSide] = mapped_column(
        SqlEnum(
            OrderSide,
            native_enum=False,
            create_constraint=False,
            length=10,
        ),
        nullable=False,
    )
    order_type: Mapped[OrderType] = mapped_column(
        SqlEnum(
            OrderType,
            native_enum=False,
            create_constraint=False,
            length=10,
        ),
        nullable=False,
    )
    time_in_force: Mapped[TimeInForce] = mapped_column(
        SqlEnum(
            TimeInForce,
            native_enum=False,
            create_constraint=False,
            length=10,
        ),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("0")
    )
    cancelled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("0")
    )
    remaining_quantity: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False
    )
    average_fill_price: Mapped[Decimal | None] = mapped_column(
        Numeric(24, 8), nullable=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        SqlEnum(
            OrderStatus,
            native_enum=False,
            create_constraint=False,
            length=30,
        ),
        nullable=False,
        default=OrderStatus.NEW,
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    account = relationship("Account", back_populates="orders")
    fills = relationship("Fill", back_populates="order")
    events = relationship("OrderEvent", back_populates="order")
