"""Upgrade a known legacy SQLite design store without rebuilding user history."""
from sqlalchemy import inspect
from pathlib import Path

def ensure_design_schema(engine):
    from .base import Base
    tables=set(inspect(engine).get_table_names())
    if engine.dialect.name=='sqlite' and 'base_portfolio_selections' in tables:
        columns={c['name']:c for c in inspect(engine).get_columns('base_portfolio_selections')}
        if not columns['expected_return']['nullable'] or not columns['volatility']['nullable']:
            from alembic.config import Config
            from alembic import command
            root=Path(__file__).resolve().parents[2]
            cfg=Config(str(root/'alembic.ini'));cfg.set_main_option('script_location',str(root/'migrations'))
            cfg.attributes['database_url']=str(engine.url)
            if 'alembic_version' not in tables:
                known=set(Base.metadata.tables)-{'portfolio_decisions','portfolio_choices'}
                if not known.issubset(tables):
                    raise RuntimeError('Legacy design schema is incomplete; run an explicit reviewed migration.')
                # Legacy design stores were created from the full 0006 ORM schema.
                command.stamp(cfg,'0006')
            command.upgrade(cfg,'head')
            with engine.connect() as con:
                if con.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
                    raise RuntimeError('Design migration failed foreign-key verification.')
    Base.metadata.create_all(engine)
    if engine.dialect.name == 'sqlite' and 'onboarding_drafts' in tables:
        columns = {c['name'] for c in inspect(engine).get_columns('onboarding_drafts')}
        if 'rebalance_frequency' not in columns:
            # Additive local upgrade: existing identities, snapshots and ledgers stay intact.
            with engine.begin() as con:
                con.exec_driver_sql('ALTER TABLE onboarding_drafts ADD COLUMN rebalance_frequency VARCHAR(16)')
