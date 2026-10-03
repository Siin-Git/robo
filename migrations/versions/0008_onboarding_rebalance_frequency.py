"""Persist draft frequency; confirmed choices live in immutable decision provenance."""
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade():
    from alembic import op
    import sqlalchemy as sa
    # Offline migrations only render SQL: their MockConnection cannot inspect
    # the database. Emit the column for the declared 0007 schema in that mode.
    # Online local ORM workspaces may already have received the additive column.
    if not op.get_context().as_sql:
        columns = sa.inspect(op.get_bind()).get_columns("onboarding_drafts")
        if "rebalance_frequency" in {column["name"] for column in columns}:
            return
    op.add_column("onboarding_drafts", sa.Column("rebalance_frequency", sa.String(16), nullable=True))

def downgrade():
    from alembic import op
    with op.batch_alter_table("onboarding_drafts") as batch:
        batch.drop_column("rebalance_frequency")
