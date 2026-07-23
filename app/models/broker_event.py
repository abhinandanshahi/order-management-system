from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.domain.enums import BrokerEventType
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ProcessedBrokerEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "processed_broker_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('FULL_FILL','PARTIAL_FILL','REJECTED','CANCELLED')",
            name="ck_processed_broker_events_type",
        ),
        CheckConstraint(
            "outcome IN ('APPLIED','IGNORED')",
            name="ck_processed_broker_events_outcome",
        ),
        Index("ix_processed_broker_events_order_id", "order_id"),
    )

    broker_event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, unique=True
    )
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[BrokerEventType] = mapped_column(
        SqlEnum(
            BrokerEventType,
            native_enum=False,
            create_constraint=False,
            length=30,
        ),
        nullable=False,
    )
    broker_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
