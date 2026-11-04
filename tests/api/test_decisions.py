from datetime import date, datetime, timezone
import json
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError
from .conftest import register, login
from src.db.models import PortfolioDecision, PortfolioChoice, Account, Order, NavDaily, Holding
from src.api.services import decision_service as svc

@pytest.fixture
def identity(client, monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    assert register(client, "decision@example.com").status_code == 201
    r=login(client,"decision@example.com")
    cookies=dict(r.cookies)
    return cookies, {"X-CSRF-Token":cookies["ra_csrf"]}

def confirm(client, identity, reason="original", adjustment=None):
    cookies,headers=identity
    frontier=client.get('/api/v1/me/frontier',cookies=cookies).json()
    return client.post('/api/v1/me/onboarding/complete',cookies=cookies,headers=headers,json={
        'frontier_id':frontier['benchmark_frontier_id'], 'theme_ids':['ai'], 'reason':reason,
        'adjustment_choice_id':adjustment})

def test_confirmation_immutable_versioned_idempotent_and_review(client,env,identity):
    c=confirm(client,identity);assert c.status_code==200,c.text
    first=c.json()['decision_id']
    assert confirm(client,identity).json()['decision_id']==first
    cookies,headers=identity
    decisions=client.get('/api/v1/me/decisions',cookies=cookies).json()['items']
    d=decisions[0];assert d['version']==1
    assert sum(d['weights'].values())==pytest.approx(1)
    assert d['expectations']['expected_return']['unit']=='fraction_per_year'
    assert d['target_effective_date'] > d['confirmed_at'][:10]
    assert d['provenance']['artifact_sha256']
    definition=d['expectations']['expected_return']['definition']
    assert definition['portfolio_reference']==first and definition['currency']=='KRW'
    assert definition['start']==d['target_effective_date']
    assert definition['cost_basis']=='EXCLUDES_TRANSACTION_COSTS'
    with env.factory() as s:
        with pytest.raises(DatabaseError):
            s.execute(text("UPDATE portfolio_decisions SET reason='changed'"))
        s.rollback()
        with pytest.raises(DatabaseError):
            s.execute(text("DELETE FROM portfolio_decisions"))
        s.rollback()
    choice={'decision_id':first,'target_id':d['target_id'],'action':'ADJUST','reason':'review risk','request_key':'adjust-001'}
    r=client.post('/api/v1/me/portfolio/choices',cookies=cookies,headers=headers,json=choice);assert r.status_code==200,r.text
    cid=r.json()['choice_id']
    assert confirm(client,identity,'revision',cid).status_code==200
    ds=client.get('/api/v1/me/decisions',cookies=cookies).json()['items']
    assert len(ds)==2 and ds[0]['previous_decision_id']==first
    assert ds[1]==d
    review=client.get(f'/api/v1/me/decisions/{first}/review',cookies=cookies)
    assert review.status_code==200,review.text
    out=review.json();assert out['review_only']
    assert out['actual']['status']=='INSUFFICIENT_HISTORY'
    assert all(x['difference'] is None for x in out['comparisons'])
    assert 'COST_BASIS_DIFFERS' in out['comparisons'][0]['reasons']
    assert all(x['status']=='NOT_REACHED' and x['cumulative_return'] is None for x in out['horizons'])
    assert client.post('/api/v1/me/portfolio/choices',cookies=cookies,headers=headers,json=choice).json()['choice_id']==cid
    assert confirm(client,identity,'other',cid).status_code==409

def test_keep_pending_adjust_stale_and_payload_conflicts(client,env,identity):
    first=confirm(client,identity).json()['decision_id'];cookies,headers=identity
    d=client.get('/api/v1/me/decisions',cookies=cookies).json()['items'][0]
    with env.factory() as s:
        s.add(Order(order_id='pending1',account_id=d['account_id'],asset_id='us_equity',side='buy',target_weight=.1,
                    submitted_at=datetime.now(timezone.utc),effective_at=date.fromisoformat(d['target_effective_date']),status='pending',created_at=datetime.now(timezone.utc)))
        s.commit()
    data={'decision_id':first,'target_id':d['target_id'],'action':'KEEP','reason':'keep weights','request_key':'keep-0001'}
    a=client.post('/api/v1/me/portfolio/choices',cookies=cookies,headers=headers,json=data);assert a.status_code==200,a.text
    assert not a.json()['effect']['target_changed'] and a.json()['effect']['pending_orders']=='continue'
    assert client.post('/api/v1/me/portfolio/choices',cookies=cookies,headers=headers,json=data).json()==a.json()
    assert client.post('/api/v1/me/portfolio/choices',cookies=cookies,headers=headers,json={**data,'reason':'other'}).status_code==409
    assert client.post('/api/v1/me/portfolio/choices',cookies=cookies,headers=headers,json={**data,'action':'ADJUST','request_key':'adjust-0001'}).json()['error']['code']=='PENDING_ORDERS'
    assert confirm(client,identity,'different').json()['error']['code']=='PENDING_ORDERS'
    assert client.post('/api/v1/me/portfolio/choices',cookies=cookies,headers=headers,json={**data,'target_id':'old','request_key':'stale-0001'}).status_code==409

def test_owner_and_legacy_no_original_estimates(client,identity,monkeypatch):
    first=confirm(client,identity).json()['decision_id']
    register(client,'other@example.com');r=login(client,'other@example.com');cookies=dict(r.cookies)
    assert client.get('/api/v1/me/decisions',cookies=cookies).json()['legacy_status']=='ORIGINAL_EXPECTATIONS_NOT_RECORDED'
    assert client.get(f'/api/v1/me/decisions/{first}/review',cookies=cookies).status_code==404

def test_actual_window_short_statistics_and_same_units(client,env,identity,monkeypatch):
    d_id=confirm(client,identity).json()['decision_id'];cookies,_=identity
    d=client.get('/api/v1/me/decisions',cookies=cookies).json()['items'][0]
    from datetime import timedelta
    start=date.fromisoformat(d['target_effective_date'])
    from src.api.services import _common as C
    monkeypatch.setattr(C, 'now_utc', lambda: datetime.combine(start+timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc))
    with env.factory() as s:
        for days,value in [(-1,50),(0,100),(1,102)]:
            day=start+timedelta(days=days)
            s.add(NavDaily(account_id=d['account_id'],date=day,nav=value,cash_balance=value,nav_base100=value,daily_return=0,cumulative_return=0,nav_status='OK',stale_price_flag=False,benchmark_version='CORE_V0.3',theme_universe_version='THEME_UNIVERSE_V0.1',risk_model_version='test',execution_rule_version='test'))
        s.commit()
    r=client.get(f'/api/v1/me/decisions/{d_id}/review',cookies=cookies);assert r.status_code==200,r.text
    out=r.json();assert out['actual']['metrics']['cumulative_return']==pytest.approx(.02)
    assert out['observation_start']==start.isoformat()
    assert out['actual']['metrics']['volatility'] is None
    assert all(x['difference'] is None for x in out['comparisons'])
    ledger=client.get('/api/v1/me/performance/ledger',cookies=cookies).json()
    assert ledger['units']['nav']=='KRW' and ledger['units']['nav_base100']=='index_100'


def test_review_excludes_future_valuations_and_does_not_reach_fake_horizons(client,env,identity):
    d_id=confirm(client,identity).json()['decision_id'];cookies,_=identity
    d=client.get('/api/v1/me/decisions',cookies=cookies).json()['items'][0]
    from datetime import timedelta
    start=date.fromisoformat(d['target_effective_date'])
    with env.factory() as s:
        for offset,value in [(0,100),(200,120)]:
            s.add(NavDaily(account_id=d['account_id'],date=start+timedelta(days=offset),nav=value,cash_balance=value,
                nav_base100=value,daily_return=0,cumulative_return=0,nav_status='OK',stale_price_flag=False,
                benchmark_version='CORE_V0.3',theme_universe_version='THEME_UNIVERSE_V0.1',risk_model_version='test',execution_rule_version='test'))
        s.commit()
    result=client.get(f'/api/v1/me/decisions/{d_id}/review',cookies=cookies).json()
    assert result['actual']['observations']==0
    assert all(h['status']=='NOT_REACHED' and h['cumulative_return'] is None for h in result['horizons'])


@pytest.mark.parametrize("change",[None,"reason","frequency","theme","changed_live_view"])
def test_reopened_identical_confirmation_with_pending_orders_uses_immutable_decision(client,env,identity,change):
    from src.db.models.onboarding import OnboardingDraft
    from src.db.models import Event
    from sqlalchemy import func
    first=confirm(client,identity).json()['decision_id']
    cookies,headers=identity
    d=client.get('/api/v1/me/decisions',cookies=cookies).json()['items'][0]
    with env.factory() as db:
        db.add(Order(order_id='reopen-pending',account_id=d['account_id'],asset_id='us_equity',side='buy',target_weight=.1,
            submitted_at=datetime.now(timezone.utc),effective_at=date.fromisoformat(d['target_effective_date']),status='pending',created_at=datetime.now(timezone.utc)))
        db.commit()
    body={'frontier_id':d['provenance']['frontier_id'],'theme_ids':['ai'],'reason':'original','rebalance_frequency':'monthly'}
    assert client.put('/api/v1/me/onboarding/draft',cookies=cookies,headers=headers,json={**body,'current_step':'review'}).status_code==200
    with env.factory() as db:
        assert db.get(OnboardingDraft,d['user_id']).completed_at is None
        before=[db.scalar(select(func.count()).select_from(model)) for model in (Order,NavDaily,Holding,Event)]
    if change=='reason': body['reason']='different grounds'
    elif change=='frequency': body['rebalance_frequency']='quarterly'
    elif change in ('theme','changed_live_view'):
        body['theme_ids']=['semiconductor']
        if change=='changed_live_view':
            from src.db.models import View
            with env.factory() as db:
                view=db.scalar(select(View).where(View.participant_id==d['participant_id'],View.end_at.is_(None)))
                view.theme_id='semiconductor'
                db.commit()
    result=client.post('/api/v1/me/onboarding/complete',cookies=cookies,headers=headers,json={**body,'expected_decision_id':first})
    if change:
        assert result.status_code==409,result.text
        assert result.json()['error']['code']=='PENDING_ORDERS'
    else:
        assert result.status_code==200,result.text
        assert result.json()['already_completed'] is True
        assert result.json()['decision_id']==first
        with env.factory() as db:
            assert db.get(OnboardingDraft,d['user_id']).completed_at is not None
    assert client.get('/api/v1/me/decisions',cookies=cookies).json()['items']==[d]
    with env.factory() as db:
        assert [db.scalar(select(func.count()).select_from(model)) for model in (Order,NavDaily,Holding,Event)]==before
        assert db.get(Order,'reopen-pending').status=='pending'
