"""Preview uses the same financial engine, with no confirmation or ledger writes."""
import pytest
from sqlalchemy import select, func
from .test_decisions import identity
from src.db.models import PortfolioDecision, PortfolioChoice, NavDaily, Order, Trade
from src.db.models.scheduled_job import ScheduledJob
from src.db.models.onboarding import OnboardingDraft


def payload(client, identity, themes=None):
    frontier = client.get('/api/v1/me/frontier', cookies=identity[0]).json()
    return {'frontier_id': frontier['benchmark_frontier_id'], 'theme_ids': ['ai'] if themes is None else themes}


@pytest.mark.parametrize('themes', [[], ['ai']])
def test_unconfirmed_comparison_does_not_write_and_matches_confirmed_pair(client, env, identity, themes):
    body = payload(client, identity, themes)
    def counts():
        with env.factory() as db:
            return [db.scalar(select(func.count()).select_from(m)) for m in (PortfolioDecision,PortfolioChoice,NavDaily,Order,Trade,ScheduledJob,OnboardingDraft)]
    before = counts()
    options = {'period': '2022', 'initial_amount': 1_000_000}
    result = client.post('/api/v1/me/onboarding/rehearsal', cookies=identity[0], json={**body,**options})
    assert result.status_code == 200, result.text
    result = result.json()
    assert result['status'] == 'AVAILABLE'
    assert result['decision_id'] is None and result['confirmed_at'] is None
    assert result['method']['allocation'] == 'UNCONFIRMED_PROPOSAL'
    assert result['actual_account_history'] is False
    assert counts() == before
    assert result == client.post('/api/v1/me/onboarding/rehearsal', cookies=identity[0], json={**body,**options}).json()
    ordinary = client.post('/api/v1/me/onboarding/preview', cookies=identity[0], json=body).json()
    assert result['proposal'] == ordinary
    for key in ('base','personalized'):
        assert result[key]['weights'] == {r['asset_id']:r['weight'] for r in ordinary[key]['weights']}
    if not themes:
        assert result['base'] == result['personalized']
    complete = client.post('/api/v1/me/onboarding/complete',cookies=identity[0],headers=identity[1],json={**body,'reason':'isolated preview choice'})
    assert complete.status_code == 200,complete.text
    decision_id=complete.json()['decision_id']
    saved=client.get(f'/api/v1/me/decisions/{decision_id}/rehearsal',cookies=identity[0],params=options).json()
    for key in ('base','personalized','series','period','source'):
        assert result[key] == saved[key]


def test_authentication_and_server_selected_weights(client, identity):
    body=payload(client,identity)
    assert client.post('/api/v1/me/onboarding/rehearsal',cookies={},json=body).status_code==401
    for extra in ({'weights':{'cash':1}},{'decision_id':'other-user'},{'initial_amount':0},{'period':'best'}):
        assert client.post('/api/v1/me/onboarding/rehearsal',cookies=identity[0],json={**body,**extra}).status_code==422
    assert client.post('/api/v1/me/onboarding/rehearsal',cookies=identity[0],json={**body,'theme_ids':['ai','ai']}).status_code==400
    assert client.post('/api/v1/me/onboarding/rehearsal',cookies=identity[0],json={**body,'frontier_id':'missing'}).status_code==404


def test_missing_prices_do_not_create_performance(client, identity, monkeypatch):
    from src.api.services import market_comparison
    body=payload(client,identity)
    # Onboarding risk preview remains valid; only retrospective price availability fails.
    monkeypatch.setattr(market_comparison,'bundle',lambda: (_ for _ in ()).throw(OSError('missing')))
    result=client.post('/api/v1/me/onboarding/rehearsal',cookies=identity[0],json=body)
    assert result.status_code==200,result.text
    data=result.json()
    assert data['status']=='UNAVAILABLE' and data['base'] is None and data['series']==[]
    assert data['proposal']['base']['frontier_id']==body['frontier_id']
