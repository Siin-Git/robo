"""0001 initial PostgreSQL schema (mirrors reverse-engineered SQLite)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from src.db.base import JSONBType, TZDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TSTZ = TZDateTime


def upgrade() -> None:
    op.create_table(
        "participants",
        sa.Column("participant_id", sa.String(16), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("join_date", sa.Date(), nullable=False),
        sa.Column("leave_date", sa.Date(), nullable=True),
        sa.Column("created_at", TSTZ, nullable=False),
        sa.Column("updated_at", TSTZ, nullable=False),
        sa.CheckConstraint("status IN ('active','inactive')", name="status_value"),
    )
    op.create_index("ix_participants_status", "participants", ["status"])

    op.create_table(
        "themes",
        sa.Column("theme_id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("theme_type", sa.String(16), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=True),
        sa.Column("market", sa.String(16), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("universe_version", sa.String(32), nullable=False),
        sa.Column("inactive_reason", sa.String(512), nullable=True),
        sa.CheckConstraint("theme_type IN ('sector','subsector','theme')",
                           name="theme_type_value"),
    )

    op.create_table(
        "accounts",
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("participant_id", sa.String(16),
                  sa.ForeignKey("participants.participant_id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("account_type", sa.String(16), nullable=False),
        sa.Column("shadow_name", sa.String(32), nullable=True),
        sa.Column("benchmark_version", sa.String(32), nullable=False),
        sa.Column("inception_date", sa.Date(), nullable=False),
        sa.Column("initial_capital_krw", sa.Numeric(24, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", TSTZ, nullable=False),
        sa.CheckConstraint("account_type IN ('core','personal','shadow')",
                           name="account_type_value"),
    )
    op.create_index("ix_accounts_participant", "accounts", ["participant_id"])
    op.create_index("ix_accounts_type", "accounts", ["account_type"])

    op.create_table(
        "views",
        sa.Column("view_id", sa.String(16), primary_key=True),
        sa.Column("participant_id", sa.String(16),
                  sa.ForeignKey("participants.participant_id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("theme_id", sa.String(64),
                  sa.ForeignKey("themes.theme_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("submitted_at", TSTZ, nullable=False),
        sa.Column("effective_at", sa.Date(), nullable=False),
        sa.Column("end_at", TSTZ, nullable=True),
        sa.Column("reason", sa.String(1024), nullable=True),
        sa.Column("theme_universe_version", sa.String(32), nullable=False),
        sa.Column("cycle_week", sa.Date(), nullable=False),
        sa.Column("cycle_date", sa.Date(), nullable=True),
        sa.CheckConstraint("status IN ('new','hold','closed','rejected')",
                           name="status_value"),
    )
    op.create_index("ix_views_participant_effective", "views", ["participant_id", "effective_at"])
    op.create_index("ix_views_status", "views", ["status"])
    op.create_index("ix_views_theme", "views", ["theme_id"])

    op.create_table(
        "portfolio_targets",
        sa.Column("target_id", sa.String(16), primary_key=True),
        sa.Column("account_id", sa.String(64),
                  sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("weights_json", JSONBType, nullable=False),
        sa.Column("core_version", sa.String(32), nullable=False),
        sa.Column("theme_universe_version", sa.String(32), nullable=False),
        sa.Column("risk_model_version", sa.String(64), nullable=False),
        sa.Column("created_at", TSTZ, nullable=False),
    )
    op.create_index("ix_targets_account_effective", "portfolio_targets",
                    ["account_id", "effective_date"])

    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(16), primary_key=True),
        sa.Column("account_id", sa.String(64),
                  sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("asset_id", sa.String(64), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("target_weight", sa.Numeric(18, 12), nullable=False),
        sa.Column("submitted_at", TSTZ, nullable=False),
        sa.Column("effective_at", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", TSTZ, nullable=False),
        sa.CheckConstraint("side IN ('buy','sell')", name="side_value"),
        sa.CheckConstraint("status IN ('pending','executed','cancelled')",
                           name="status_value"),
    )
    op.create_index("ix_orders_account_status", "orders", ["account_id", "status"])
    op.create_index("ix_orders_effective", "orders", ["effective_at"])

    op.create_table(
        "trades",
        sa.Column("trade_id", sa.String(16), primary_key=True),
        sa.Column("order_id", sa.String(16),
                  sa.ForeignKey("orders.order_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_id", sa.String(64),
                  sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("asset_id", sa.String(64), nullable=False),
        sa.Column("execution_at", sa.Date(), nullable=False),
        sa.Column("execution_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("gross_value", sa.Numeric(24, 4), nullable=False),
        sa.Column("transaction_cost", sa.Numeric(24, 8), nullable=False),
        sa.Column("net_value", sa.Numeric(24, 4), nullable=False),
    )
    op.create_index("ix_trades_account_execution", "trades", ["account_id", "execution_at"])

    op.create_table(
        "holdings_daily",
        sa.Column("account_id", sa.String(64),
                  sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"),
                  primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("asset_id", sa.String(64), primary_key=True),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("market_value", sa.Numeric(24, 4), nullable=False),
        sa.Column("weight", sa.Numeric(18, 12), nullable=False),
    )
    op.create_index("ix_holdings_account_date", "holdings_daily", ["account_id", "date"])

    op.create_table(
        "nav_daily",
        sa.Column("account_id", sa.String(64),
                  sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"),
                  primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("nav", sa.Numeric(24, 8), nullable=False),
        sa.Column("nav_base100", sa.Numeric(24, 8), nullable=False),
        sa.Column("daily_return", sa.Numeric(18, 12), nullable=True),
        sa.Column("cumulative_return", sa.Numeric(18, 12), nullable=False),
        sa.Column("cash_balance", sa.Numeric(24, 4), nullable=False),
        sa.Column("stale_price_flag", sa.Boolean(), nullable=False),
        sa.Column("nav_status", sa.String(16), nullable=False),
        sa.Column("benchmark_version", sa.String(32), nullable=False),
        sa.Column("theme_universe_version", sa.String(32), nullable=False),
        sa.Column("risk_model_version", sa.String(64), nullable=False),
        sa.Column("execution_rule_version", sa.String(64), nullable=False),
        sa.CheckConstraint("nav_status IN ('OK','STALE_PRICE','NAV_INCOMPLETE')",
                           name="nav_status_value"),
    )
    op.create_index("ix_nav_account_date", "nav_daily", ["account_id", "date"])

    op.create_table(
        "performance_daily",
        sa.Column("account_id", sa.String(64),
                  sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"),
                  primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("metrics_json", JSONBType, nullable=False),
    )

    op.create_table(
        "prices_daily",
        sa.Column("asset_id", sa.String(64), primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
    )

    op.create_table(
        "events",
        sa.Column("event_id", sa.String(16), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("participant_id", sa.String(16),
                  sa.ForeignKey("participants.participant_id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("account_id", sa.String(64),
                  sa.ForeignKey("accounts.account_id", ondelete="RESTRICT"), nullable=True),
        sa.Column("timestamp", TSTZ, nullable=False),
        sa.Column("payload_json", JSONBType, nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
    )
    op.create_index("ix_events_timestamp", "events", ["timestamp"])
    op.create_index("ix_events_type", "events", ["event_type"])
    op.create_index("ix_events_participant", "events", ["participant_id"])
    op.create_index("ix_events_account", "events", ["account_id"])

    op.create_table(
        "model_versions",
        sa.Column("version_id", sa.String(64), primary_key=True),
        sa.Column("version_type", sa.String(32), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("created_at", TSTZ, nullable=False),
        sa.Column("payload_json", JSONBType, nullable=False),
    )

    op.create_table(
        "counters",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("value", sa.Integer(), nullable=False),
    )

    op.create_table(
        "forward_state",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.String(256), nullable=True),
        sa.Column("updated_at", TSTZ, nullable=True),
    )


def downgrade() -> None:
    for table in ("forward_state", "counters", "model_versions", "events", "prices_daily",
                  "performance_daily", "nav_daily", "holdings_daily", "trades", "orders",
                  "portfolio_targets", "views", "accounts", "themes", "participants"):
        op.drop_table(table)
