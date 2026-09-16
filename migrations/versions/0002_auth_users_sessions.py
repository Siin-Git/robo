"""0002 auth users + sessions (additive only; 0001 untouched)."""
from __future__ import annotations

from src.db.base import JSONBType, TZDateTime  # noqa: F401 (documents shared types)

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(16), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("email_normalized", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("participant_id", sa.String(16),
                  sa.ForeignKey("participants.participant_id", ondelete="RESTRICT"),
                  nullable=True, unique=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", TZDateTime, nullable=True),
        sa.Column("created_at", TZDateTime, nullable=False),
        sa.Column("updated_at", TZDateTime, nullable=False),
        sa.Column("last_login_at", TZDateTime, nullable=True),
        sa.Column("password_changed_at", TZDateTime, nullable=True),
        sa.CheckConstraint("role IN ('user','admin')", name="role_value"),
        sa.CheckConstraint("status IN ('active','disabled')", name="status_value"),
    )
    op.create_index("ix_users_status", "users", ["status"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(16), primary_key=True),
        sa.Column("user_id", sa.String(16),
                  sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", TZDateTime, nullable=False),
        sa.Column("expires_at", TZDateTime, nullable=False),
        sa.Column("last_seen_at", TZDateTime, nullable=True),
        sa.Column("revoked_at", TZDateTime, nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
    )
    op.create_index("ix_sessions_user", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires", "sessions", ["expires_at"])
    op.create_index("ix_sessions_revoked", "sessions", ["revoked_at"])


def downgrade() -> None:
    from alembic import op
    op.drop_table("sessions")
    op.drop_table("users")
