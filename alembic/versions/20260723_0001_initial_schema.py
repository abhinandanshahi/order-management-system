"""Initial OMS schema.

Revision ID: 20260723_0001
Revises: None
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260723_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MONEY = sa.Numeric(24, 8)


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("cash_balance", MONEY, nullable=False),
        sa.Column("reserved_cash", MONEY, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cash_balance >= 0", name="ck_accounts_cash_nonnegative"),
        sa.CheckConstraint("reserved_cash >= 0", name="ck_accounts_reserved_nonnegative"),
        sa.CheckConstraint(
            "reserved_cash <= cash_balance",
            name="ck_accounts_reserved_not_above_cash",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])

    op.create_table(
        "market_prices",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("price", MONEY, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price > 0", name="ck_market_prices_price_positive"),
        sa.PrimaryKeyConstraint("symbol"),
    )

    op.create_table(
        "orders",
        sa.Column("client_order_id", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=10), nullable=False),
        sa.Column("time_in_force", sa.String(length=10), nullable=False),
        sa.Column("quantity", MONEY, nullable=False),
        sa.Column("price", MONEY, nullable=False),
        sa.Column("filled_quantity", MONEY, nullable=False),
        sa.Column("cancelled_quantity", MONEY, nullable=False),
        sa.Column("remaining_quantity", MONEY, nullable=False),
        sa.Column("average_fill_price", MONEY, nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("broker_order_id", sa.String(length=100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_orders_quantity_positive"),
        sa.CheckConstraint("price > 0", name="ck_orders_price_positive"),
        sa.CheckConstraint("filled_quantity >= 0", name="ck_orders_filled_nonnegative"),
        sa.CheckConstraint("cancelled_quantity >= 0", name="ck_orders_cancelled_nonnegative"),
        sa.CheckConstraint("remaining_quantity >= 0", name="ck_orders_remaining_nonnegative"),
        sa.CheckConstraint(
            "filled_quantity + cancelled_quantity + remaining_quantity = quantity",
            name="ck_orders_quantity_conservation",
        ),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_orders_side"),
        sa.CheckConstraint("order_type IN ('MARKET', 'LIMIT')", name="ck_orders_type"),
        sa.CheckConstraint("time_in_force IN ('DAY', 'GTC', 'IOC')", name="ck_orders_tif"),
        sa.CheckConstraint(
            "status IN ('NEW','VALIDATED','ROUTED','PARTIALLY_FILLED','FILLED',"
            "'REJECTED','CANCEL_PENDING','CANCELLED')",
            name="ck_orders_status",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "client_order_id", name="uq_orders_account_client_order"),
        sa.UniqueConstraint(
            "account_id",
            "idempotency_key",
            name="uq_orders_account_idempotency_key",
        ),
    )
    op.create_index("ix_orders_account_status", "orders", ["account_id", "status"])
    op.create_index("ix_orders_expires_at", "orders", ["expires_at"])
    op.create_index("ix_orders_symbol", "orders", ["symbol"])

    op.create_table(
        "positions",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("net_quantity", MONEY, nullable=False),
        sa.Column("average_entry_price", MONEY, nullable=False),
        sa.Column("realized_pnl", MONEY, nullable=False),
        sa.Column("unrealized_pnl", MONEY, nullable=False),
        sa.Column("last_mark_price", MONEY, nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "average_entry_price >= 0",
            name="ck_positions_average_price_nonnegative",
        ),
        sa.CheckConstraint(
            "last_mark_price IS NULL OR last_mark_price > 0",
            name="ck_positions_mark_price_positive",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "symbol", name="uq_positions_account_symbol"),
    )
    op.create_index("ix_positions_symbol", "positions", ["symbol"])

    op.create_table(
        "fills",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("broker_event_id", sa.Uuid(), nullable=False),
        sa.Column("execution_id", sa.String(length=100), nullable=False),
        sa.Column("quantity", MONEY, nullable=False),
        sa.Column("price", MONEY, nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_fills_quantity_positive"),
        sa.CheckConstraint("price > 0", name="ck_fills_price_positive"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_event_id"),
        sa.UniqueConstraint("execution_id"),
    )
    op.create_index("ix_fills_order_id", "fills", ["order_id"])

    op.create_table(
        "order_events",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=True),
        sa.Column("event_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_events_order_created", "order_events", ["order_id", "created_at"])

    op.create_table(
        "processed_broker_events",
        sa.Column("broker_event_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("broker_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('FULL_FILL','PARTIAL_FILL','REJECTED','CANCELLED')",
            name="ck_processed_broker_events_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('APPLIED','IGNORED')",
            name="ck_processed_broker_events_outcome",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("broker_event_id"),
    )
    op.create_index("ix_processed_broker_events_order_id", "processed_broker_events", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_processed_broker_events_order_id", table_name="processed_broker_events")
    op.drop_table("processed_broker_events")
    op.drop_index("ix_order_events_order_created", table_name="order_events")
    op.drop_table("order_events")
    op.drop_index("ix_fills_order_id", table_name="fills")
    op.drop_table("fills")
    op.drop_index("ix_positions_symbol", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_orders_symbol", table_name="orders")
    op.drop_index("ix_orders_expires_at", table_name="orders")
    op.drop_index("ix_orders_account_status", table_name="orders")
    op.drop_table("orders")
    op.drop_table("market_prices")
    op.drop_index("ix_accounts_user_id", table_name="accounts")
    op.drop_table("accounts")
