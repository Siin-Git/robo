"""0005 onboarding drafts (additive)."""
from __future__ import annotations

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op
    from src.db.base import JSONBType, TZDateTime
    op.create_table(
        "onboarding_drafts",
        sa.Column("user_id", sa.String(16), primary_key=True),
        sa.Column("participant_id", sa.String(16), nullable=False),
        sa.Column("frontier_id", sa.String(16), nullable=True),
        sa.Column("frontier_version", sa.String(32), nullable=True),
        sa.Column("theme_ids_json", JSONBType, nullable=False),
        sa.Column("reason", sa.String(1024), nullable=True),
        sa.Column("current_step", sa.String(16), nullable=False),
        sa.Column("created_at", TZDateTime, nullable=False),
        sa.Column("updated_at", TZDateTime, nullable=False),
        sa.Column("completed_at", TZDateTime, nullable=True),
    )


def downgrade() -> None:
    from alembic import op
    op.drop_table("onboarding_drafts")
