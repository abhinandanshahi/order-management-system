from decimal import Decimal

from app.domain.enums import OrderSide
from app.domain.position_rules import (
    calculate_position_after_fill,
    calculate_unrealized_pnl,
)

ZERO = Decimal("0")


def test_weighted_average_price_for_additional_long_fill() -> None:
    result = calculate_position_after_fill(
        current_quantity=Decimal("10"),
        current_average_price=Decimal("100"),
        current_realized_pnl=ZERO,
        side=OrderSide.BUY,
        fill_quantity=Decimal("20"),
        fill_price=Decimal("110"),
    )
    assert result.net_quantity == Decimal("30")
    assert result.average_entry_price == Decimal("106.6666666666666666666666667")
    assert result.realized_pnl == ZERO


def test_partial_long_close_realizes_profit() -> None:
    result = calculate_position_after_fill(
        current_quantity=Decimal("10"),
        current_average_price=Decimal("100"),
        current_realized_pnl=ZERO,
        side=OrderSide.SELL,
        fill_quantity=Decimal("4"),
        fill_price=Decimal("125"),
    )
    assert result.net_quantity == Decimal("6")
    assert result.average_entry_price == Decimal("100")
    assert result.realized_pnl == Decimal("100")


def test_trade_can_cross_from_long_to_short() -> None:
    result = calculate_position_after_fill(
        current_quantity=Decimal("5"),
        current_average_price=Decimal("100"),
        current_realized_pnl=ZERO,
        side=OrderSide.SELL,
        fill_quantity=Decimal("8"),
        fill_price=Decimal("90"),
    )
    assert result.net_quantity == Decimal("-3")
    assert result.average_entry_price == Decimal("90")
    assert result.realized_pnl == Decimal("-50")


def test_unrealized_pnl_uses_signed_quantity() -> None:
    long_pnl = calculate_unrealized_pnl(
        net_quantity=Decimal("10"),
        average_entry_price=Decimal("100"),
        mark_price=Decimal("110"),
    )
    short_pnl = calculate_unrealized_pnl(
        net_quantity=Decimal("-10"),
        average_entry_price=Decimal("100"),
        mark_price=Decimal("90"),
    )
    assert long_pnl == Decimal("100")
    assert short_pnl == Decimal("100")
