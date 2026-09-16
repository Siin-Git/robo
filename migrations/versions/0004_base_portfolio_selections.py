"""0004 base portfolio selections on Efficient Frontier (additive)."""
from __future__ import annotations

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op
    from src.db.base import JSONBType, TZDateTime
    op.create_table(
        "base_portfolio_selections",
        sa.Column("selection_id", sa.String(16), primary_key=True),
        sa.Column("user_id", sa.String(16), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("participant_id", sa.String(16), sa.ForeignKey("participants.participant_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("frontier_version", sa.String(32), nullable=False),
        sa.Column("frontier_id", sa.String(16), nullable=False),
        sa.Column("expected_return", sa.Numeric(18, 12), nullable=False),
        sa.Column("volatility", sa.Numeric(18, 12), nullable=False),
        sa.Column("sharpe", sa.Numeric(18, 12), nullable=True),
        sa.Column("weights_json", JSONBType, nullable=False),
        sa.Column("selected_at", TZDateTime, nullable=False),
        sa.Column("effective_at", TZDateTime, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.CheckConstraint("status IN ('active','superseded')", name="status_value"),
    )
    op.create_index("ix_base_sel_user", "base_portfolio_selections", ["user_id"])
    op.create_index("ix_base_sel_participant", "base_portfolio_selections", ["participant_id"])
    op.create_index("ix_base_sel_frontier", "base_portfolio_selections", ["frontier_version", "frontier_id"])


def downgrade() -> None:
    from alembic import op
    op.drop_table("base_portfolio_selections")
