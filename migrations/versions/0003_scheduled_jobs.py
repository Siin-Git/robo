"""0003 scheduled jobs registry (additive only; 0001/0002 untouched)."""
from __future__ import annotations

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op
    from src.db.base import JSONBType, TZDateTime
    op.create_table(
        "scheduled_jobs",
        sa.Column("job_id", sa.String(32), primary_key=True),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("started_at", TZDateTime, nullable=True),
        sa.Column("completed_at", TZDateTime, nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error_message", sa.String(2048), nullable=True),
        sa.Column("github_run_id", sa.String(64), nullable=True),
        sa.Column("stats_json", JSONBType, nullable=False),
        sa.CheckConstraint("status IN ('running','success','failed','skipped')",
                           name="status_value"),
    )
    op.create_index("ix_jobs_type_scheduled", "scheduled_jobs", ["job_type", "scheduled_for"])
    op.create_index("ix_jobs_status", "scheduled_jobs", ["status"])


def downgrade() -> None:
    from alembic import op
    op.drop_table("scheduled_jobs")
