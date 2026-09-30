"""0006 demo cohorts and slots (additive).

두 테이블은 ORM 모델(``src/db/models/demo_cohort.py``)에만 있고 마이그레이션에
빠져 있었다. SQLite 로 개발할 때는 ``Base.metadata.create_all`` 이 만들어 줘서
드러나지 않지만, PostgreSQL 배포는 ``alembic upgrade head`` 로만 스키마를
만든다. 그대로 올리면 초대 슬롯과 비교군 정원을 쓰는 화면이 런타임에 죽는다.

``tests/db/test_migration_covers_models.py`` 가 이 누락을 다시 잡는다.
"""
from __future__ import annotations

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import sqlalchemy as sa
    from alembic import op
    from src.db.base import JSONBType, TZDateTime
    op.create_table(
        "demo_cohorts",
        sa.Column("cohort_id", sa.String(64), primary_key=True),
        sa.Column("prepared_count", sa.Integer, nullable=False),
        sa.Column("created_at", TZDateTime, nullable=False),
    )
    op.create_table(
        "demo_slots",
        sa.Column("slot_id", sa.String(80), primary_key=True),
        sa.Column("cohort_id", sa.String(64),
                  sa.ForeignKey("demo_cohorts.cohort_id"), nullable=False),
        sa.Column("slot_number", sa.Integer, nullable=False),
        sa.Column("invite_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("email_normalized", sa.String(320), nullable=False),
        sa.Column("user_id", sa.String(16),
                  sa.ForeignKey("users.user_id"), nullable=True, unique=True),
        sa.Column("draft_json", JSONBType, nullable=False),
        sa.Column("configuration_json", JSONBType, nullable=True),
        sa.Column("report_json", JSONBType, nullable=True),
        sa.Column("confirmed_at", TZDateTime, nullable=True),
        sa.Column("forward_started_at", TZDateTime, nullable=True),
        sa.UniqueConstraint("cohort_id", "slot_number"),
    )


def downgrade() -> None:
    from alembic import op
    op.drop_table("demo_slots")
    op.drop_table("demo_cohorts")
