"""Real-ledger API contracts, isolated SQLite only; no price replay fixtures."""
from datetime import date
import json

import pytest
from sqlalchemy import select
from src.db.models import Account, NavDaily, PortfolioDecision
from .conftest import login, register
from .test_pending_decision_performance import add_valuation, clock


def confirmed(client, monkeypatch, email, day='2026-09-30'):
    monkeypatch.setenv('ALLOW_PUBLIC_REGISTRATION', 'true')
    clock(monkeypatch, day)
    assert register(client, email, display_name=email.split('@')[0]).status_code == 201
    cookies = dict(login(client, email).cookies)
    f = client.get('/api/v1/me/frontier', cookies=cookies).json()
    response = client.post('/api/v1/me/onboarding/complete', cookies=cookies,
        headers={'X-CSRF-Token': cookies['ra_csrf']},
        json={'frontier_id':f['benchmark_frontier_id'], 'theme_ids':[], 'reason':'TEST ONLY'})
    assert response.status_code == 200
    d = client.get('/api/v1/me/decisions', cookies=cookies).json()['items'][0]
    return cookies, d


def seed(factory, decision, values, core=True):
    with factory() as s:
        accounts = s.scalars(select(Account).where(Account.participant_id==decision['participant_id'])).all()
        for account in accounts:
            if account.account_type == 'personal' or core:
                for day, value in values:
                    add_valuation(s, account.account_id, day, value if account.account_type=='personal' else 100)
        s.commit()


def get_comparison(client, cookies, suffix=''):
    r=client.get('/api/v1/me/performance/comparison'+suffix, cookies=cookies)
    assert r.status_code==200, r.text
    return r.json()


@pytest.mark.parametrize('basis', ['return', 'mdd', 'volatility'])
def test_interior_drawdown_survives_common_window_and_missing_peer_day(client, env, monkeypatch, basis):
    a, da = confirmed(client, monkeypatch, 'drawdown-a@example.com')
    b, db = confirmed(client, monkeypatch, 'drawdown-b@example.com')
    seed(env.factory, da, [('2026-10-01', 100), ('2026-10-02', 50), ('2026-10-05', 100)])
    seed(env.factory, db, [('2026-10-01', 100), ('2026-10-05', 101)])
    clock(monkeypatch, '2026-10-05')
    result = get_comparison(client, a, '?basis=' + basis)
    rows = {r['participant_id']: r for r in result['items']}
    first, second = rows[da['participant_id']], rows[db['participant_id']]
    assert first['metrics']['mdd'] == pytest.approx(-.5)
    assert result['dates'] == ['2026-10-01', '2026-10-02', '2026-10-05']
    assert (result['start'], result['end']) == ('2026-10-01', '2026-10-05')
    assert first['observations'] == 3
    assert second['observations'] == 2
    assert second['metrics']['mdd'] == 0  # observed-only, not evidence of no intervening loss
    assert [p['personal_index100'] for p in first['series']] == [100, 50, 100]
    assert [p['personal_index100'] for p in second['series']] == [100, None, 101]
    assert second['metric_quality']['mdd']['reason'] == 'OBSERVATION_GAPS'
    assert second['quality']['missing_comparison_dates'] == ['2026-10-02']
    if basis == 'return':
        assert (first['rank'], second['rank']) == (2, 1)
        assert first['metrics']['cumulative_return'] == 0
        assert second['metrics']['cumulative_return'] == pytest.approx(.01)
    else:
        assert result['ranked'] == 0
        assert all(r['rank'] is None for r in rows.values())
    for cookies, row in [(a, first), (b, second)]:
        individual = client.get('/api/v1/me/performance/dashboard', cookies=cookies).json()
        common = client.get('/api/v1/me/performance/dashboard?comparison=common', cookies=cookies).json()
        contribution = client.get('/api/v1/me/performance/contributions?comparison=common', cookies=cookies).json()
        assert individual['metrics'] == common['metrics'] == row['metrics']
        assert common['observations'] == row['observations']
        assert contribution['cumulative_return'] == common['metrics']['cumulative_return']
        assert [p['date'] for p in contribution['history']] == [p['date'] for p in common['series']]
        assert contribution['reconciliation']['reconciled'] is True
        if row is first:
            assert common['series'][1]['personal'] == pytest.approx(-.5)
            assert contribution['history'][1]['cumulative_return'] == pytest.approx(-.5)
            assert sum(contribution['history'][1]['contributions'].values()) == pytest.approx(-.5)


@pytest.mark.parametrize('gap,stale', [(False, False), (True, False), (False, True)])
def test_mdd_short_history_can_be_measured_but_ranking_requires_quality(client, env, monkeypatch, gap, stale):
    a, da = confirmed(client, monkeypatch, 'quality-a@example.com')
    _, db = confirmed(client, monkeypatch, 'quality-b@example.com')
    end = '2026-10-05' if gap else '2026-10-02'
    for d in [da, db]:
        seed(env.factory, d, [('2026-10-01', 100), (end, 90)])
    if stale:
        with env.factory() as s:
            row = s.get(NavDaily, (da['account_id'], date.fromisoformat(end)))
            row.nav_status = 'STALE_PRICE'
            s.commit()
    clock(monkeypatch, '2026-10-05')
    result = get_comparison(client, a, '?basis=mdd')
    assert result['ranked'] == (0 if gap or stale else 2)
    assert all(r['metrics']['mdd'] == pytest.approx(-.1) for r in result['items'])
    assert all(r['metrics']['volatility'] is None for r in result['items'])
    if gap:
        assert all(r['metric_quality']['mdd']['reason'] == 'OBSERVATION_GAPS' for r in result['items'])
        assert result['dates'] == ['2026-10-01', '2026-10-02', '2026-10-05']
        assert all(r['series'][1]['personal_index100'] is None for r in result['items'])
    if stale:
        mine = next(r for r in result['items'] if r['participant_id'] == da['participant_id'])
        assert mine['metric_quality']['mdd']['reason'] == 'STALE_VALUATIONS'
        assert mine['metric_quality']['mdd']['status'] == 'OBSERVED_ONLY'


def test_annual_volatility_preserves_every_daily_return_and_rejects_missing_observation(client, env, monkeypatch):
    import pandas as pd
    a, da = confirmed(client, monkeypatch, 'daily-a@example.com')
    _, db = confirmed(client, monkeypatch, 'daily-b@example.com')
    days = [d.date().isoformat() for d in pd.bdate_range('2026-10-01', periods=32)]
    for d, scale in [(da, 1), (db, 2)]:
        seed(env.factory, d, [(day, 100 + i * scale + (-1)**i) for i, day in enumerate(days)])
    clock(monkeypatch, days[-1])
    a = dict(login(client, 'daily-a@example.com').cookies)
    result = get_comparison(client, a, '?basis=volatility')
    assert result['ranked'] == 2
    assert all(r['metric_quality']['volatility']['rankable'] for r in result['items'])
    mine = next(r for r in result['items'] if r['participant_id'] == da['participant_id'])
    own = client.get('/api/v1/me/performance/dashboard?comparison=common', cookies=a).json()
    assert mine['metrics'] == own['metrics']
    with env.factory() as s:
        s.delete(s.get(NavDaily, (db['account_id'], date.fromisoformat(days[5]))))
        s.commit()
    after = get_comparison(client, a, '?basis=volatility')
    first = next(r for r in after['items'] if r['participant_id'] == da['participant_id'])
    second = next(r for r in after['items'] if r['participant_id'] == db['participant_id'])
    assert first['observations'] == 32
    assert first['metrics'] == mine['metrics']
    assert second['observations'] == 31  # enough returns alone is not sufficient
    assert second['metrics']['volatility'] is None
    assert second['metric_quality']['volatility']['reason'] == 'OBSERVATION_GAPS'
    assert second['series'][5]['personal_index100'] is None
    assert after['ranked'] == 0


def test_common_dates_rebase_same_metrics_contributions_and_refresh(client, env, monkeypatch):
    a, da = confirmed(client, monkeypatch, 'first@example.com')
    b, db = confirmed(client, monkeypatch, 'second@example.com', '2026-10-01')
    seed(env.factory, da, [('2026-09-30',50),('2026-10-01',100),('2026-10-02',110),('2026-10-05',121)])
    seed(env.factory, db, [('2026-10-02',200),('2026-10-05',210)])
    clock(monkeypatch,'2026-10-06')
    for period in ['ALL','1M','3M']:
        comparison=get_comparison(client,a,'?period='+period)
        assert comparison['data_source']=='ACCOUNT_LEDGER'
        assert comparison['dates']==['2026-10-02','2026-10-05']
        assert comparison['ranked']==2
        first=next(r for r in comparison['items'] if r['participant_id']==da['participant_id'])
        assert first['rank']==1
        assert first['metrics']['cumulative_return']==pytest.approx(.1)
        assert first['series'][0]['personal_index100']==100
        own=client.get('/api/v1/me/performance/dashboard?comparison=common&period='+period,cookies=a).json()
        assert own['metrics']==first['metrics']
        assert (own['start'],own['end'])==(comparison['start'],comparison['end'])
        contribution=client.get('/api/v1/me/performance/contributions?comparison=common&period='+period,cookies=a).json()
        assert contribution['cumulative_return']==own['metrics']['cumulative_return']
        assert contribution['reconciliation']['reconciled'] is True
        assert contribution['comparison_window']==own['comparison_window']
        assert own['valuation']['nav_krw']==121
    individual=client.get('/api/v1/me/performance/dashboard',cookies=a).json()
    assert individual['start']=='2026-10-01'  # pre-effective row excluded
    assert individual['metrics']['cumulative_return']==pytest.approx(.21)
    seed(env.factory,da,[('2026-10-06',132)])
    seed(env.factory,db,[('2026-10-06',240)])
    refreshed=get_comparison(client,a)
    assert refreshed['end']=='2026-10-06'
    assert refreshed['dates']==['2026-10-02','2026-10-05','2026-10-06']
    assert next(r for r in refreshed['items'] if r['participant_id']==db['participant_id'])['metrics']['cumulative_return']==pytest.approx(.2)
    assert 'own_report' not in refreshed
    for key in ['email','password','nav_krw','cash_krw','account_id','decision_id','weights','holdings']:
        assert key not in json.dumps(refreshed)
    assert client.get(f"/api/v1/participants/{db['participant_id']}/performance/ledger",cookies=a).status_code==403
    assert client.get(f"/api/v1/me/decisions/{db['decision_id']}/review",cookies=a).status_code==404


@pytest.mark.parametrize('count', [0,1,2])
def test_zero_one_two_observations_no_fake_returns_or_ranks(client,env,monkeypatch,count):
    a, da=confirmed(client,monkeypatch,'short@example.com')
    seed(env.factory,da,[('2026-10-01',100),('2026-10-02',102)][:count])
    clock(monkeypatch,'2026-10-04')
    own=client.get('/api/v1/me/performance/dashboard',cookies=a).json()
    assert own['observations']==count
    assert own['metrics']['volatility'] is None
    assert own['metrics']['cumulative_return']==(pytest.approx(.02) if count==2 else None)
    assert own['valuation'] is None if count==0 else own['valuation']['nav_krw']==([100,102][count-1])
    if count==1:
        assert own['valuation']['index100']==100
        assert own['series']==[]
        assert own['assets']==[]
    compare=get_comparison(client,a)
    assert compare['ranked']==0
    assert all(row['rank'] is None for row in compare['items'])
    assert compare['reason']=='INSUFFICIENT_PARTICIPANTS'
    assert all(row['metrics']['cumulative_return'] is None for row in compare['items'])
    common=client.get('/api/v1/me/performance/dashboard?comparison=common',cookies=a).json()
    assert common['comparison_window']['status']=='UNAVAILABLE'
    assert common['comparison_window']['reason']==compare['items'][0]['reason']


@pytest.mark.parametrize('other_dates', [['2026-10-05','2026-10-06'],['2026-10-02','2026-10-05']])
def test_no_overlap_or_single_common_point_never_rank(client,env,monkeypatch,other_dates):
    a, da=confirmed(client,monkeypatch,'a@example.com')
    _, db=confirmed(client,monkeypatch,'b@example.com')
    seed(env.factory,da,[('2026-10-01',100),('2026-10-02',110)])
    seed(env.factory,db,list(zip(other_dates,[100,110])))
    clock(monkeypatch,'2026-10-07')
    a=dict(login(client,'a@example.com').cookies)
    result=get_comparison(client,a)
    assert result['reason']=='NO_COMMON_PERIOD'
    assert result['ranked']==0
    assert all(r['metrics']['cumulative_return'] is None for r in result['items'])


def test_core_missing_and_short_risk_do_not_invent_values(client,env,monkeypatch):
    a, da=confirmed(client,monkeypatch,'a@example.com')
    _, db=confirmed(client,monkeypatch,'b@example.com')
    for d in [da,db]:
        seed(env.factory,d,[('2026-10-01',100),('2026-10-02',110)],core=False)
    clock(monkeypatch,'2026-10-04')
    assert get_comparison(client,a)['ranked']==2  # real zero/nonzero returns can rank
    for basis,reason in [('excess','CORE_SAME_PERIOD_MISSING'),('volatility','RISK_HISTORY_INSUFFICIENT')]:
        result=get_comparison(client,a,'?basis='+basis)
        assert result['ranked']==0
        assert all(r['reason']==reason for r in result['items'])
    own=client.get('/api/v1/me/performance/dashboard',cookies=a).json()
    assert own['metrics']['benchmark_return'] is None
    assert all(p['benchmark'] is None for p in own['series'])


def test_pending_transition_retains_previous_review_and_excludes_future(client,env,monkeypatch):
    a, da=confirmed(client,monkeypatch,'a@example.com')
    _, db=confirmed(client,monkeypatch,'b@example.com')
    for d in [da,db]: seed(env.factory,d,[('2026-10-01',100),('2026-10-02',102)])
    clock(monkeypatch,'2026-10-03')
    f=client.get('/api/v1/me/frontier',cookies=a).json()
    r=client.post('/api/v1/me/onboarding/complete',cookies=a,headers={'X-CSRF-Token':a['ra_csrf']},
        json={'frontier_id':f['benchmark_frontier_id'],'theme_ids':['ai'],'reason':'test revision','expected_decision_id':da['decision_id']})
    assert r.status_code==200
    seed(env.factory,da,[('2026-10-05',200)])
    before=get_comparison(client,a)
    assert before['ranked']==2
    assert before['end']=='2026-10-02'
    clock(monkeypatch,'2026-10-05')
    after=get_comparison(client,a)
    mine=next(row for row in after['items'] if row['participant_id']==da['participant_id'])
    assert mine['reason']=='ONE_VALUATION'
    assert mine['rank'] is None
    own=client.get('/api/v1/me/performance/dashboard',cookies=a).json()
    assert own['observations']==1
    assert own['decision_context']['previous_decision']['decision_id']==da['decision_id']
    old=client.get(f"/api/v1/me/decisions/{da['decision_id']}/review",cookies=a).json()
    assert old['actual']['observations']==2


def test_auth_registry_not_disabled_operating_mirrors_and_invalid_inputs(client,env,monkeypatch,tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.db.base import Base
    from src.db.models import User
    from src.api.services.ledger_comparison_service import overview
    a, da=confirmed(client,monkeypatch,'a@example.com')
    _, db=confirmed(client,monkeypatch,'b@example.com')
    for d in [da,db]: seed(env.factory,d,[('2026-10-01',100),('2026-10-02',110)])
    clock(monkeypatch,'2026-10-04')
    assert client.get('/api/v1/me/performance/comparison?period=YTD',cookies=a).status_code==400
    assert client.get('/api/v1/me/performance/comparison?basis=sharpe',cookies=a).status_code==400
    assert client.get('/api/v1/me/performance/dashboard?comparison=bad',cookies=a).status_code==400
    engine=create_engine('sqlite:///'+str(tmp_path/'independent-auth.db'))
    Base.metadata.create_all(engine)
    with env.factory() as operating,sessionmaker(bind=engine)() as auth:
        from src.db.models import Participant
        for cls in [Participant,User]:
            for row in operating.scalars(select(cls)):
                auth.add(cls(**{c.name:getattr(row,c.name) for c in cls.__table__.columns}))
        auth.commit()
        for user in operating.scalars(select(User)): user.status='disabled'
        operating.commit()
        result=overview(auth,operating)
        assert result['ranked']==2
        auth.scalar(select(User).where(User.participant_id==db['participant_id'])).status='disabled'
        auth.commit()
        assert overview(auth,operating)['registered']==1
    assert client.get('/api/v1/me/performance/comparison',cookies=a).status_code==403  # disabled local test account


def test_active_cohort_includes_prepared_and_enrolled_users_only(client,env,monkeypatch):
    from src.local.capstone import EMAILS
    from src.db.models import User
    from src.db.models.demo_cohort import DemoCohort,DemoSlot
    from src.db.models.operational import ForwardState
    from src.api.services.enrollment_service import ACTIVE_KEY
    from src.api.services.ledger_comparison_service import members
    from src.api.services import _common as C
    monkeypatch.setenv('ALLOW_PUBLIC_REGISTRATION','true')
    for email in [EMAILS[0],EMAILS[1],'outsider@example.com']:
        assert register(client,email).status_code==201
    monkeypatch.setenv('CAPSTONE_DEMO','1')
    monkeypatch.setenv('APP_PROFILE','local')
    with env.factory() as s:
        users={u.email:u for u in s.scalars(select(User))}
        s.add(DemoCohort(cohort_id='comparison-test',prepared_count=1,created_at=C.now_utc()))
        s.flush()
        s.add(ForwardState(key=ACTIVE_KEY,value='comparison-test',updated_at=C.now_utc()))
        s.add(DemoSlot(slot_id='comparison-test:2',cohort_id='comparison-test',slot_number=2,
            email_normalized=EMAILS[1],user_id=users[EMAILS[1]].user_id,
            invite_hash='TEST_FIXTURE_HASH_ONLY',draft_json={}))
        s.commit()
        assert {p.participant_id for p in members(s)}=={users[EMAILS[0]].participant_id,users[EMAILS[1]].participant_id}
