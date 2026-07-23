from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    initial_cash_balance: Decimal = Field(gt=0, decimal_places=8)
    currency: str = Field(default="INR", min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    currency: str
    cash_balance: Decimal
    reserved_cash: Decimal
    available_cash: Decimal
    created_at: datetime
    updated_at: datetime
