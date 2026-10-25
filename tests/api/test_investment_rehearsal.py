"""Isolated counterfactual tests; the real ledger is never a fixture."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select, func

from .conftest import register, login
from .test_decisions import confirm, identity
from src.api.services import rehearsal_service as svc, decision_service, market_comparison
from src.db.models import PortfolioDecision, PortfolioChoice, NavDaily, Order, Trade
from src.db.models.scheduled_job import ScheduledJob


@pytest.fixture
def pair(client, identity):
    response = confirm(client, identity)
    assert response.status_code == 200, response.text
    return client.get('/api/v1/me/decisions', cookies=identity[0]).json()['items'][0]


def read(client, identity, pair, **params):
    return client.get(f"/api/v1/me/decisions/{pair['decision_id']}/rehearsal", cookies=identity[0], params=params)


@pytest.fixture
def known(monkeypatch):
    dates = pd.bdate_range('2020-01-01', periods=31)
    prices = pd.DataFrame({'stock': [100, 120, 90] + [110] * 28}, index=dates, dtype=float)
    decision = SimpleNamespace(decision_id='saved', confirmed_at=pd.Timestamp('2026-10-01', tz='UTC'),
        reason='saved reason', provenance_json={'base_weights': {'stock': 1}}, weights_json={'stock': 1})
    monkeypatch.setattr(decision_service, 'own', lambda *args: decision)
    monkeypatch.setattr(market_comparison, 'bundle', lambda: (prices, {'version': 'SYNTHETIC_TEST_ONLY'}))
    return prices, decision


def test_known_peak_to_trough_same_weights_and_scale(known):
    result = svc.rehearsal(None, 'user', 'saved', initial_amount=1_000_000)
    assert result['status'] == 'AVAILABLE'
    assert result['base'] == result['personalized']
    assert result['base']['end_value'] == pytest.approx(1_100_000)
    assert result['base']['cumulative_return'] == pytest.approx(.1)
    assert result['base']['max_drawdown'] == pytest.approx(-.25)
    assert result['series'][2]['base_drawdown'] == pytest.approx(-.25)
    twice = svc.rehearsal(None, 'user', 'saved', initial_amount=2_000_000)
    assert twice['base']['end_value'] == 2 * result['base']['end_value']
    assert twice['base']['max_drawdown'] == result['base']['max_drawdown']
    assert twice['base']['cumulative_return'] == result['base']['cumulative_return']


def test_cash_mixed_allocation_and_saved_pair_not_current_selection(known):
    prices, decision = known
    decision.weights_json = {'stock': .5, 'cash': .5}
    result = svc.rehearsal(None, 'user', 'saved', initial_amount=1_000_000)
    assert result['personalized']['end_value'] == pytest.approx(1_050_000)
    # 1.1m peak -> .95m trough, not a weighted average of the stock drawdown.
    assert result['personalized']['max_drawdown'] == pytest.approx(.95 / 1.1 - 1)
    decision.weights_json = {'cash': 1}
    cash = svc.rehearsal(None, 'user', 'saved')
    assert cash['personalized']['cumulative_return'] == 0
    assert cash['personalized']['max_drawdown'] == 0


@pytest.mark.parametrize('weights', [None, {}, {'stock': .5}, {'stock': -1, 'cash': 2},
                                    {'stock': float('nan')}, {'stock': True}, {'stock': '1'}])
def test_missing_invalid_original_never_falls_back(known, weights):
    _, decision = known
    decision.provenance_json['base_weights'] = weights
    result = svc.rehearsal(None, 'user', 'saved')
    assert result['status'] == 'UNAVAILABLE'
    assert result['base'] is None and result['personalized'] is None and result['series'] == []


@pytest.mark.parametrize('bad', [np.nan, np.inf, 0, -1])
def test_bad_price_is_not_filled_or_dropped(known, bad):
    prices, _ = known
    prices.loc[prices.index[2], 'stock'] = bad
    result = svc.rehearsal(None, 'user', 'saved')
    assert result['status'] == 'UNAVAILABLE' and not result['series']


def test_missing_asset_and_insufficient_history(known, monkeypatch):
    prices, decision = known
    decision.weights_json = {'unavailable': 1}
    result = svc.rehearsal(None, 'user', 'saved')
    assert result['status'] == 'UNAVAILABLE'
    assert result['base'] is None
    monkeypatch.setattr(market_comparison, 'bundle', lambda: (prices.iloc[:30], {}))
    assert svc.rehearsal(None, 'user', 'saved')['periods'] == []


def test_authenticated_owner_read_is_repeatable_and_does_not_write(client, env, identity, pair):
    models = (PortfolioDecision, PortfolioChoice, NavDaily, Order, Trade, ScheduledJob)
    def snapshot():
        with env.factory() as db:
            return [db.scalar(select(func.count()).select_from(m)) for m in models]
    before = snapshot()
    result = read(client, identity, pair)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['status'] == 'AVAILABLE'
    assert data['kind'] == 'HISTORICAL_REHEARSAL' and data['actual_account_history'] is False
    assert data['base']['weights'] == pair['provenance']['base_weights']
    assert data['personalized']['weights'] == pair['weights']
    assert data['series'][0]['base_value'] == pytest.approx(10_000_000)
    assert data['series'][0]['personalized_value'] == pytest.approx(10_000_000)
    assert len(data['series']) == data['period']['observations']
    assert data == read(client, identity, pair).json()
    assert snapshot() == before
    assert client.get('/api/v1/me/decisions', cookies=identity[0]).json()['items'][0] == pair
    url = f"/api/v1/me/decisions/{pair['decision_id']}/rehearsal"
    assert client.get(url, cookies={}).status_code == 401
    register(client, 'rehearsal-other@example.com')
    other = dict(login(client, 'rehearsal-other@example.com').cookies)
    assert client.get(url, cookies=other).status_code == 404
    assert client.get('/api/v1/me/decisions/missing/rehearsal', cookies=identity[0]).status_code == 404


def test_all_calendar_years_and_period_reset_use_real_bundle(client, identity, pair):
    result = read(client, identity, pair).json()
    prices, _ = market_comparison.bundle()
    assert [p['id'] for p in result['periods']] == ['all'] + [str(y) for y in sorted(set(prices.index.year))]
    assert '일부' in result['periods'][1]['label'] and '일부' in result['periods'][-1]['label']
    year = read(client, identity, pair, period='2022').json()
    assert year['period']['start'].startswith('2022') and year['period']['end'].startswith('2022')
    assert year['series'][0]['base_value'] == pytest.approx(result['initial_amount'])
    weights = pair['provenance']['base_weights']
    first, last = prices.loc[year['period']['start']], prices.loc[year['period']['end']]
    expected = sum(w * (last[a] / first[a] if a != 'cash' else 1) for a, w in weights.items() if w)
    assert year['base']['end_value'] == pytest.approx(expected * result['initial_amount'])


@pytest.mark.parametrize('params', [{'period': '1900'}, {'period': 'best'}, {'initial_amount': 0},
                                    {'initial_amount': 'nan'}, {'initial_amount': '10000.5'},
                                    {'initial_amount': 1_000_000_001}])
def test_query_constraints(client, identity, pair, params):
    assert read(client, identity, pair, **params).status_code == 422
