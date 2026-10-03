"""Only disposable databases; frequency is confirmed, versioned and user-owned."""
from datetime import date, datetime, timezone
import sqlite3
import pytest
from .conftest import register, login
from .test_decisions import identity
from .test_lab_meeting import lab, login as lab_login
from src.api.services import _common as C
from src.forward.decision_policy import rebalance_frequency


@pytest.mark.parametrize('frequency', ['monthly', 'quarterly'])
def test_0008_adopts_local_column_without_changing_confirmed_history(client, env, identity, frequency):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    from sqlalchemy import text

    cookies, headers = identity
    fid = client.get('/api/v1/me/frontier', cookies=cookies).json()['benchmark_frontier_id']
    body = dict(frontier_id=fid, theme_ids=['ai'], reason='preserve original', rebalance_frequency=frequency)
    assert client.put('/api/v1/me/onboarding/draft', cookies=cookies, headers=headers, json=body).status_code == 200
    confirmed = client.post('/api/v1/me/onboarding/complete', cookies=cookies, headers=headers, json=body)
    assert confirmed.status_code == 200, confirmed.text
    original = client.get('/api/v1/me/decisions', cookies=cookies).json()
    with env.factory() as session:
        before = {table: session.execute(text(f'SELECT * FROM {table}')).all()
                  for table in ('users', 'onboarding_drafts', 'portfolio_decisions', 'portfolio_targets', 'orders')}
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / 'alembic.ini'))
    config.attributes['database_url'] = f'sqlite:///{env.dbfile}'
    # Model-created local SQLite already has the nullable column but is behind
    # the formal revision, just like a local additive upgrade at revision 0007.
    command.stamp(config, '0007')
    command.upgrade(config, 'head')
    command.upgrade(config, 'head')
    with env.factory() as session:
        assert {table: session.execute(text(f'SELECT * FROM {table}')).all()
                for table in before} == before
        assert session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0008'
        assert session.execute(text('PRAGMA foreign_key_check')).all() == []
    assert client.get('/api/v1/me/decisions', cookies=cookies).json() == original
    assert client.get('/api/v1/me/portfolio/summary', cookies=cookies).json()['rebalance_frequency'] == frequency

def test_draft_confirmation_reload_login_and_version_preserve_frequency(client, env, identity, monkeypatch):
    cookies, headers = identity
    monkeypatch.setattr(C, 'now_utc', lambda: datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert client.get('/api/v1/me/onboarding/draft', cookies=cookies).json()['rebalance_frequency'] == 'monthly'
    fid = client.get('/api/v1/me/frontier', cookies=cookies).json()['benchmark_frontier_id']
    body = dict(frontier_id=fid, theme_ids=['ai'], reason='original', rebalance_frequency='quarterly')
    saved = client.put('/api/v1/me/onboarding/draft', cookies=cookies, headers=headers, json={**body, 'current_step': 'themes'})
    assert saved.status_code == 200, saved.text
    # An old client partially updating another draft field must retain the choice.
    client.put('/api/v1/me/onboarding/draft', cookies=cookies, headers=headers, json={'current_step':'review'})
    assert client.get('/api/v1/me/onboarding/draft', cookies=cookies).json()['rebalance_frequency'] == 'quarterly'
    confirmed = client.post('/api/v1/me/onboarding/complete', cookies=cookies, headers=headers, json=body)
    assert confirmed.status_code == 200, confirmed.text
    first = confirmed.json()['decision_id']
    assert confirmed.json()['rebalance_frequency'] == 'quarterly'
    assert client.post('/api/v1/me/onboarding/complete', cookies=cookies, headers=headers, json=body).json()['decision_id'] == first
    old = client.get('/api/v1/me/decisions', cookies=cookies).json()['items'][0]
    assert old['provenance']['rebalance_frequency'] == 'quarterly'
    client.post('/api/v1/auth/logout', cookies=cookies, headers=headers)
    logged = login(client, 'decision@example.com'); cookies=dict(logged.cookies); headers={'X-CSRF-Token':cookies['ra_csrf']}
    assert client.get('/api/v1/me/onboarding/draft', cookies=cookies).json()['rebalance_frequency'] == 'quarterly'
    assert client.get('/api/v1/me/portfolio/summary', cookies=cookies).json()['rebalance_frequency'] == 'quarterly'
    monkeypatch.setattr(C, 'now_utc', lambda: datetime(2026, 10, 3, tzinfo=timezone.utc))
    logged = login(client, 'decision@example.com'); cookies=dict(logged.cookies); headers={'X-CSRF-Token':cookies['ra_csrf']}
    changed = client.post('/api/v1/me/onboarding/complete', cookies=cookies, headers=headers, json={**body,'rebalance_frequency':'monthly'})
    assert changed.status_code == 200, changed.text
    rows = client.get('/api/v1/me/decisions', cookies=cookies).json()['items']
    assert len(rows) == 2 and rows[1] == old
    assert rows[0]['provenance']['rebalance_frequency'] == 'monthly'
    # Future confirmations do not immediately change the currently operating cycle.
    with sqlite3.connect(env.dbfile) as con:
        con.row_factory=sqlite3.Row
        assert rebalance_frequency(con, old['account_id'], '2026-10-04') == 'quarterly'
        assert rebalance_frequency(con, old['account_id'], '2026-10-05') == 'monthly'
    from src.db.models import NavDaily
    with env.factory() as session:
        session.add(NavDaily(account_id=old['account_id'],date=date(2026,10,2),nav=100,cash_balance=100,
            nav_base100=100,daily_return=0,cumulative_return=0,nav_status='OK',stale_price_flag=False,
            benchmark_version='CORE_V0.3',theme_universe_version='THEME_UNIVERSE_V0.1',
            risk_model_version='TEST',execution_rule_version='TEST'))
        session.commit()
    class TestDate(date):
        @classmethod
        def today(cls):
            return cls(2026,10,4)
    monkeypatch.setattr('src.api.services.ledger_service.date',TestDate)
    monkeypatch.setattr(C,'now_utc',lambda:datetime(2026,10,4,tzinfo=timezone.utc))
    assert client.get('/api/v1/me/ledger/status',cookies=cookies).json()['next_rebalance_date']=='2027-01-01'
    monkeypatch.setattr(C,'now_utc',lambda:datetime(2026,10,5,tzinfo=timezone.utc))
    assert client.get('/api/v1/me/ledger/status',cookies=cookies).json()['next_rebalance_date']=='2026-11-02'
    register(client, 'frequency-other@example.com')
    other = dict(login(client,'frequency-other@example.com').cookies)
    assert client.get('/api/v1/me/onboarding/draft', cookies=other).json()['rebalance_frequency'] == 'monthly'
    assert client.get('/api/v1/me/portfolio/summary', cookies=other).json()['rebalance_frequency'] is None

@pytest.mark.parametrize('route,method', [('/draft','put'),('/complete','post')])
@pytest.mark.parametrize('frequency', ['weekly', '', 'MONTHLY'])
def test_invalid_frequency_is_rejected_without_saving(client, identity, route, method, frequency):
    cookies, headers = identity
    body = {'frontier_id':'F001','rebalance_frequency':frequency}
    response = getattr(client,method)('/api/v1/me/onboarding'+route,cookies=cookies,headers=headers,json=body)
    assert response.status_code == 422
    assert client.get('/api/v1/me/onboarding/draft',cookies=cookies).json()['rebalance_frequency'] == 'monthly'

def test_reserved_first_setup_retains_draft_frequency_when_confirmation_omits_it(lab):
    env,passwords=lab
    from src.local.capstone import EMAILS
    client=env.client;headers=lab_login(client,EMAILS[0],passwords[EMAILS[0]])
    fid=client.get('/api/v1/me/frontier').json()['benchmark_frontier_id']
    body={'frontier_id':fid,'theme_ids':['ai']}
    saved=client.put('/api/v1/me/onboarding/draft',headers=headers,json={**body,'rebalance_frequency':'quarterly'})
    assert saved.status_code==200
    confirmed=client.post('/api/v1/me/onboarding/complete',headers=headers,json=body)
    assert confirmed.status_code==200,confirmed.text
    assert confirmed.json()['rebalance_frequency']=='quarterly'
    assert client.get('/api/v1/me/onboarding/draft').json()['rebalance_frequency']=='quarterly'
    assert client.get('/api/v1/me/portfolio/summary').json()['rebalance_frequency']=='quarterly'
