"""Persist draft frequency; confirmed choices live in immutable decision provenance."""
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade():
    from alembic import op
    import sqlalchemy as sa
    # Local ORM workspaces may already have received the additive column.
    if 'rebalance_frequency' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('onboarding_drafts')}:
        op.add_column("onboarding_drafts", sa.Column("rebalance_frequency", sa.String(16), nullable=True))

def downgrade():
    from alembic import op
    with op.batch_alter_table("onboarding_drafts") as batch:
        batch.drop_column("rebalance_frequency")
