from decimal import Decimal

from app.domain.enums import OrderSide
from app.domain.exceptions import InsufficientBuyingPower
from app.domain.order_rules import (
    ensure_sufficient_buying_power,
    required_buying_power,
)


def test_buy_order_reserves_full_notional() -> None:
    assert required_buying_power(
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        price=Decimal("2500.25"),
    ) == Decimal("25002.50")


def test_sell_order_does_not_reserve_cash() -> None:
    assert required_buying_power(
        side=OrderSide.SELL,
        quantity=Decimal("10"),
        price=Decimal("2500.25"),
    ) == Decimal("0")


def test_insufficient_buying_power_is_a_domain_error() -> None:
    import pytest

    with pytest.raises(InsufficientBuyingPower):
        ensure_sufficient_buying_power(
            available_cash=Decimal("99"),
            required_cash=Decimal("100"),
        )
