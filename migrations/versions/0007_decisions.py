"""Immutable confirmed decisions and user choices; no legacy backfill."""
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade():
    from alembic import op
    import sqlalchemy as sa
    with op.batch_alter_table("base_portfolio_selections") as batch:
        batch.alter_column("expected_return", existing_type=sa.Numeric(18,12), nullable=True)
        batch.alter_column("volatility", existing_type=sa.Numeric(18,12), nullable=True)
    from src.db.models.decision import PortfolioDecision, PortfolioChoice
    PortfolioDecision.__table__.create(op.get_bind(), checkfirst=True)
    PortfolioChoice.__table__.create(op.get_bind(), checkfirst=True)

def downgrade():
    from alembic import op
    op.drop_table("portfolio_choices")
    op.drop_table("portfolio_decisions")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION portfolio_choices_immutable()")
        op.execute("DROP FUNCTION portfolio_decisions_immutable()")
