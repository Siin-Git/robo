"""Isolated owner case projection; these generated test prices are not operating data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select, func
from .conftest import register, login
from .test_decisions import identity, confirm
from src.api.services import _common as C
from src.api.services import internal_tracking_service as tracking
from src.db.models import PortfolioDecision, PriceDaily, Event, Order, NavDaily


def setup_case(client, env, identity, monkeypatch, source='market-provider', values=(100,110)):
    monkeypatch.setattr(C,'now_utc',lambda:datetime(2026,9,1,2,tzinfo=timezone.utc))
    did=confirm(client,identity).json()['decision_id']
    path=f'/api/v1/me/decisions/{did}/asset-review-case'
    response=client.get(path,cookies=identity[0]);assert response.status_code==200,response.text
    initial=response.json()
    start=C.as_date(initial['window_start'])
    with env.factory() as db:
        for offset,value in enumerate(values):
            db.add(PriceDaily(asset_id=initial['asset_id'],date=start+timedelta(days=offset),price=value,source=source))
        db.add(PriceDaily(asset_id=initial['asset_id'],date=start-timedelta(days=1),price=999,source=source))
        db.add(PriceDaily(asset_id=initial['asset_id'],date=start+timedelta(days=20),price=999,source=source))
        db.commit()
    monkeypatch.setattr(C,'now_utc',lambda:datetime.combine(start+timedelta(days=2),datetime.min.time(),tzinfo=timezone.utc))
    return did,path,initial


def test_stored_estimate_prices_and_defer_are_read_only(client,env,identity,monkeypatch):
    did,path,initial=setup_case(client,env,identity,monkeypatch)
    def state():
        with env.factory() as db:
            return (deepcopy(db.get(PortfolioDecision,did).provenance_json),
                [db.scalar(select(func.count()).select_from(model)) for model in (Event,Order,NavDaily)])
    before=state()
    result=client.get(path,cookies=identity[0]).json()
    assert result['initial_estimate']==initial['initial_estimate']
    assert result['observation']['count']==2
    assert result['observation']['first_price']==100
    assert result['observation']['last_price']==110
    assert result['observation']['price_return']==pytest.approx(.1)
    assert result['assessment']['action']=='DEFER'
    assert result['assessment']['recorded_human_review'] is False
    assert {'HORIZON_NOT_REACHED','COMPARISON_DEFINITION_PENDING'}.issubset({r['code'] for r in result['assessment']['reasons']})
    if initial['initial_estimate']['volatility'] is None:
        assert 'INITIAL_ESTIMATE_MISSING' in {r['code'] for r in result['assessment']['reasons']}
    assert result['changes_model_or_orders'] is False
    assert 'reviews' not in result and 'snapshot' not in result and 'participant_id' not in result
    from src.api.services import portfolio_service
    monkeypatch.setattr(portfolio_service,'_expected_return',lambda *args:999)
    assert client.get(path,cookies=identity[0]).json()['initial_estimate']==initial['initial_estimate']
    assert state()==before


def test_case_requires_owner_and_admin_route_stays_private(client,env,identity,monkeypatch):
    did,path,_=setup_case(client,env,identity,monkeypatch)
    assert client.get(path,cookies={}).status_code==401
    assert register(client,'another-case@example.com').status_code==201
    other=dict(login(client,'another-case@example.com').cookies)
    assert client.get(path,cookies=other).status_code==404
    assert client.get(f'/api/v1/admin/tracking/{did}',cookies=identity[0]).status_code==403


@pytest.mark.parametrize('source',['SYNTHETIC_TEST_CASE','synthetic:v2','HISTORICAL_REPLAY','fixture','test-provider',''])
def test_rejects_non_operating_sources(client,env,identity,monkeypatch,source):
    _,path,_=setup_case(client,env,identity,monkeypatch,source)
    result=client.get(path,cookies=identity[0]).json()
    assert result['observation']['excluded'] is True
    assert result['observation']['count']==0 and result['observation']['curve']==[]
    assert result['observation']['price_return'] is None
    assert all(h['status']=='UNVERIFIED' for h in result['horizons'])


def test_missing_original_is_not_rebuilt_and_single_price_is_not_zero_return(client,env,identity,monkeypatch):
    monkeypatch.setattr(tracking,'snapshot',lambda *args:{'assets':[]})
    _,path,_=setup_case(client,env,identity,monkeypatch,values=(100,))
    result=client.get(path,cookies=identity[0]).json()
    assert result['initial_estimate'] is None
    assert result['observation']['count']==1 and result['observation']['price_return'] is None
    assert {'INITIAL_ESTIMATE_MISSING','INSUFFICIENT_OBSERVATIONS'}.issubset({r['code'] for r in result['assessment']['reasons']})


def test_later_decision_stops_observations_and_selection_ignores_returns(client,env,identity,monkeypatch):
    did,path,initial=setup_case(client,env,identity,monkeypatch)
    # Insert a separate superseding fixture snapshot; never alter the original.
    with env.factory() as db:
        d=db.get(PortfolioDecision,did)
        next_d=PortfolioDecision(**{column.name:deepcopy(getattr(d,column.name)) for column in PortfolioDecision.__table__.columns})
        next_d.decision_id='case-superseding';next_d.version=d.version+1
        next_d.effective_date=C.as_date(initial['window_start'])+timedelta(days=1)
        db.add(next_d);db.commit()
    result=client.get(path,cookies=identity[0]).json()
    assert result['window_status']=='SUPERSEDED'
    assert result['observation']['count']==1
    assert result['asset_id']==initial['asset_id']


def test_complete_saved_base_estimate_is_preferred_and_remains_immutable(client,env,identity,monkeypatch):
    original_snapshot=tracking.snapshot
    def fixture_snapshot(*args):
        # A complete synthetic forecast is captured only in this isolated test.
        result=original_snapshot(*args)
        for a in result['assets']:
            if a['asset_id'] != 'cash' and not a['asset_id'].startswith('theme:'):
                a['expected_return']=.06
                a['volatility']=.15
        return result
    monkeypatch.setattr(tracking,'snapshot',fixture_snapshot)
    did,path,initial=setup_case(client,env,identity,monkeypatch)
    result=client.get(path,cookies=identity[0]).json()
    assert not result['asset_id'].startswith('theme:')
    assert result['initial_estimate']['expected_return']==.06
    assert result['initial_estimate']['volatility']==.15
    assert 'INITIAL_ESTIMATE_MISSING' not in {r['code'] for r in result['assessment']['reasons']}
    monkeypatch.setattr(tracking,'snapshot',lambda *args:{'assets':[]})
    assert client.get(path,cookies=identity[0]).json()['initial_estimate']==initial['initial_estimate']
