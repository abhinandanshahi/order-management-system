from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    symbol: str
    net_quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    last_mark_price: Decimal | None
    updated_at: datetime


class PnLSummaryResponse(BaseModel):
    account_id: UUID
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
