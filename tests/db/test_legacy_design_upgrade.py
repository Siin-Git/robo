import subprocess,sys,os
import pytest
from sqlalchemy import create_engine,inspect,text
from src.db.design_schema import ensure_design_schema

def test_known_legacy_workspace_is_upgraded_without_fabricating_decisions(tmp_path):
    url=f'sqlite:///{tmp_path/"legacy.db"}'
    env=dict(os.environ,DATABASE_BACKEND='sqlite',DATABASE_URL=url);env.pop('CAPSTONE_DEMO',None);env.pop('CAPSTONE_DESIGN_DATABASE_URL',None)
    r=subprocess.run([sys.executable,'-m','alembic','upgrade','0006'],env=env,capture_output=True,text=True);assert r.returncode==0,r.stderr
    e=create_engine(url)
    # Existing operational metadata must survive, not be seeded or rewritten.
    with e.begin() as con:
        con.execute(text("INSERT INTO forward_state VALUES('preserved','legacy-record','2026-09-01 00:00:00')"))
        con.execute(text('DROP TABLE alembic_version'))
    ensure_design_schema(e);ensure_design_schema(e)
    columns={c['name']:c for c in inspect(e).get_columns('base_portfolio_selections')}
    assert columns['expected_return']['nullable'] and columns['volatility']['nullable']
    with e.connect() as con:
        assert con.execute(text("SELECT value FROM forward_state WHERE key='preserved'")).scalar_one()=='legacy-record'
        assert con.execute(text('SELECT COUNT(*) FROM portfolio_decisions')).scalar_one()==0
        assert con.exec_driver_sql('PRAGMA foreign_key_check').fetchall()==[]

def test_existing_0007_store_gains_frequency_without_rewriting_history(tmp_path):
    url=f'sqlite:///{tmp_path/"previous.db"}'
    env=dict(os.environ,DATABASE_BACKEND='sqlite',DATABASE_URL=url)
    env.pop('CAPSTONE_DEMO',None);env.pop('CAPSTONE_DESIGN_DATABASE_URL',None)
    r=subprocess.run([sys.executable,'-m','alembic','upgrade','0007'],env=env,capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    engine=create_engine(url)
    with engine.begin() as con:
        con.execute(text("INSERT INTO forward_state VALUES('preserved','old-record','2026-09-01 00:00:00')"))
        con.execute(text("INSERT INTO onboarding_drafts (user_id,participant_id,theme_ids_json,current_step,created_at,updated_at) VALUES ('old','P001','[]','themes','2026-09-01','2026-09-01')"))
    ensure_design_schema(engine);ensure_design_schema(engine)
    with engine.connect() as con:
        assert con.execute(text("SELECT value FROM forward_state WHERE key='preserved'")).scalar_one()=='old-record'
        assert con.execute(text("SELECT rebalance_frequency FROM onboarding_drafts WHERE user_id='old'")).scalar_one() is None
    # Applying the formal migration after the local additive upgrade must also work.
    r=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,capture_output=True,text=True)
    assert r.returncode==0,r.stderr


@pytest.mark.parametrize('existing_frequency', ['column_missing', None, 'monthly', 'quarterly'])
def test_0008_online_preserves_existing_rows_and_frequency(tmp_path, existing_frequency):
    url = f'sqlite:///{tmp_path / "frequency.db"}'
    env = dict(os.environ, DATABASE_BACKEND='sqlite', DATABASE_URL=url)
    env.pop('CAPSTONE_DEMO', None)
    env.pop('CAPSTONE_DESIGN_DATABASE_URL', None)
    command = [sys.executable, '-m', 'alembic', 'upgrade']
    result = subprocess.run(command + ['0007'], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    with engine.begin() as con:
        con.execute(text("INSERT INTO forward_state VALUES('preserved','old-record','2026-09-01 00:00:00')"))
        con.execute(text("INSERT INTO onboarding_drafts (user_id,participant_id,theme_ids_json,reason,current_step,created_at,updated_at) VALUES ('old','P001','[\"ai\"]','keep draft','themes','2026-09-01','2026-09-02')"))
    if existing_frequency != 'column_missing':
        # The existing local additive-upgrade path does not stamp Alembic.
        ensure_design_schema(engine)
        with engine.begin() as con:
            con.execute(text("UPDATE onboarding_drafts SET rebalance_frequency=:frequency"),
                        {'frequency': existing_frequency})
    old_columns = [c['name'] for c in inspect(engine).get_columns('onboarding_drafts')]
    with engine.connect() as con:
        old_draft = con.execute(text('SELECT ' + ','.join(old_columns) + ' FROM onboarding_drafts')).one()
        old_state = con.execute(text('SELECT * FROM forward_state')).all()
    for _ in range(2):
        result = subprocess.run(command + ['head'], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    columns = inspect(engine).get_columns('onboarding_drafts')
    assert [c['name'] for c in columns].count('rebalance_frequency') == 1
    assert next(c for c in columns if c['name'] == 'rebalance_frequency')['nullable']
    with engine.connect() as con:
        assert con.execute(text('SELECT ' + ','.join(old_columns) + ' FROM onboarding_drafts')).one() == old_draft
        assert con.execute(text('SELECT * FROM forward_state')).all() == old_state
        assert con.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0008'
        expected = None if existing_frequency == 'column_missing' else existing_frequency
        assert con.execute(text('SELECT rebalance_frequency FROM onboarding_drafts')).scalar_one() == expected
        assert con.exec_driver_sql('PRAGMA foreign_key_check').all() == []
    engine.dispose()
