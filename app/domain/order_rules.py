from decimal import Decimal

from app.domain.enums import OrderSide
from app.domain.exceptions import InsufficientBuyingPower

ZERO = Decimal("0")


def required_buying_power(
    *,
    side: OrderSide,
    quantity: Decimal,
    price: Decimal,
) -> Decimal:
    if side != OrderSide.BUY:
        return ZERO
    return quantity * price


def ensure_sufficient_buying_power(
    *,
    available_cash: Decimal,
    required_cash: Decimal,
) -> None:
    if required_cash > available_cash:
        raise InsufficientBuyingPower()
