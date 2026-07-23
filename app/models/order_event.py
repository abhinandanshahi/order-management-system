from uuid import UUID

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Index, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain.enums import OrderEventType, OrderStatus
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class OrderEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_events"
    __table_args__ = (
        Index("ix_order_events_order_created", "order_id", "created_at"),
    )

    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[OrderEventType] = mapped_column(
        SqlEnum(
            OrderEventType,
            native_enum=False,
            create_constraint=False,
            length=50,
        ),
        nullable=False,
    )
    previous_status: Mapped[OrderStatus | None] = mapped_column(
        SqlEnum(
            OrderStatus,
            native_enum=False,
            create_constraint=False,
            length=30,
        ),
        nullable=True,
    )
    new_status: Mapped[OrderStatus | None] = mapped_column(
        SqlEnum(
            OrderStatus,
            native_enum=False,
            create_constraint=False,
            length=30,
        ),
        nullable=True,
    )
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    order = relationship("Order", back_populates="events")
