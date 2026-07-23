from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import OrderSide

ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class PositionCalculation:
    net_quantity: Decimal
    average_entry_price: Decimal
    realized_pnl: Decimal


def calculate_position_after_fill(
    *,
    current_quantity: Decimal,
    current_average_price: Decimal,
    current_realized_pnl: Decimal,
    side: OrderSide,
    fill_quantity: Decimal,
    fill_price: Decimal,
) -> PositionCalculation:
    signed_fill = fill_quantity if side == OrderSide.BUY else -fill_quantity

    if current_quantity == ZERO or current_quantity * signed_fill > ZERO:
        new_quantity = current_quantity + signed_fill
        total_cost = (
            abs(current_quantity) * current_average_price
            + abs(signed_fill) * fill_price
        )
        return PositionCalculation(
            net_quantity=new_quantity,
            average_entry_price=total_cost / abs(new_quantity),
            realized_pnl=current_realized_pnl,
        )

    closing_quantity = min(abs(current_quantity), abs(signed_fill))
    if current_quantity > ZERO:
        pnl_delta = (fill_price - current_average_price) * closing_quantity
    else:
        pnl_delta = (current_average_price - fill_price) * closing_quantity

    new_quantity = current_quantity + signed_fill
    if new_quantity == ZERO:
        average_price = ZERO
    elif current_quantity * new_quantity > ZERO:
        average_price = current_average_price
    else:
        average_price = fill_price

    return PositionCalculation(
        net_quantity=new_quantity,
        average_entry_price=average_price,
        realized_pnl=current_realized_pnl + pnl_delta,
    )


def calculate_unrealized_pnl(
    *,
    net_quantity: Decimal,
    average_entry_price: Decimal,
    mark_price: Decimal | None,
) -> Decimal:
    if mark_price is None or net_quantity == ZERO:
        return ZERO
    return (mark_price - average_entry_price) * net_quantity
