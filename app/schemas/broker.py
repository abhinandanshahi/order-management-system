from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import BrokerEventType, OrderSide, TimeInForce


class BrokerOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: UUID
    symbol: str
    side: OrderSide
    time_in_force: TimeInForce
    quantity: Decimal
    remaining_quantity: Decimal
    price: Decimal


class BrokerExecutionEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: BrokerEventType
    order_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    filled_quantity: Decimal = Decimal("0")
    fill_price: Decimal | None = None
    execution_id: str | None = None
    reason: str | None = None

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Broker event timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_fill_payload(self) -> "BrokerExecutionEvent":
        if self.event_type in {
            BrokerEventType.FULL_FILL,
            BrokerEventType.PARTIAL_FILL,
        }:
            if self.filled_quantity <= 0:
                raise ValueError("Filled quantity must be positive for a fill event")
            if self.fill_price is None or self.fill_price <= 0:
                raise ValueError("Fill price must be positive for a fill event")
            if not self.execution_id:
                raise ValueError("Execution ID is required for a fill event")
        return self
