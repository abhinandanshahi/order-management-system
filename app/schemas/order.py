from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import OrderSide, OrderStatus, OrderType, TimeInForce


class OrderCreate(BaseModel):
    client_order_id: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=100)
    account_id: UUID
    symbol: str = Field(min_length=1, max_length=32)
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce
    quantity: Decimal = Field(gt=0, decimal_places=8)
    price: Decimal = Field(gt=0, decimal_places=8)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_order_id: str
    account_id: UUID
    symbol: str
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce
    quantity: Decimal
    price: Decimal
    filled_quantity: Decimal
    cancelled_quantity: Decimal
    remaining_quantity: Decimal
    average_fill_price: Decimal | None
    status: OrderStatus
    rejection_reason: str | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CancelOrderResponse(BaseModel):
    order_id: UUID
    status: OrderStatus
    message: str


class FillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    broker_event_id: UUID
    execution_id: str
    quantity: Decimal
    price: Decimal
    executed_at: datetime


class OrderEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    event_type: str
    previous_status: OrderStatus | None
    new_status: OrderStatus | None
    event_data: dict
    created_at: datetime
