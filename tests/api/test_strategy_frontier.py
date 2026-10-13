import copy
import numpy as np
import pandas as pd
import pytest
from src.api.services import strategy_frontier_service as svc
from src.api.services.strategy_service import bundle
from .test_decisions import identity


def test_actual_compositions_have_separate_returns_and_covariance_weighted_risk(client, identity):
    cookies, _ = identity
    assert client.get('/api/v1/strategies/frontier-comparison', cookies={}).status_code == 401
    r = client.get('/api/v1/strategies/frontier-comparison', cookies=cookies)
    assert r.status_code == 200
    data = r.json()
    assert data['period']['observations'] == 97
    assert not data['actual_account_history'] and not data['confirmation_eligible']
    a,b = data['items']
    assert a['expected_return'] != b['expected_return']
    assert a['volatility'] != b['volatility']
    assert a['snapshot_date'] == '2026-10-01' and b['snapshot_date'] == '2026-09-03'
    for p in (a,b):
        assert sum(w['weight'] for w in p['weights']) == pytest.approx(1)
        assert p['sharpe'] == pytest.approx((p['expected_return']-.03)/p['volatility'])
    # Independent weighted series check, no frontend coordinates or Korean equity proxy.
    raw = __import__('json').loads((svc.C.ROOT / svc.ARTIFACT).read_text())
    returns = pd.DataFrame({t:pd.Series(v['prices'],dtype=float).rename_axis('date').pipe(lambda s:s.set_axis(pd.to_datetime(s.index))).resample('W-FRI').last().pct_change(fill_method=None) for t,v in raw['prices'].items()}).dropna()
    for p in (a,b):
        portfolio = sum(returns[w['ticker']]*w['weight'] for w in p['weights'] if w['ticker']!='cash')
        assert p['expected_return'] == pytest.approx(portfolio.mean()*52)
        from sklearn.covariance import LedoitWolf
        stock_cov = LedoitWolf().fit(returns).covariance_ * 52
        vector = np.array([next((w['weight'] for w in p['weights'] if w['ticker']==t),0) for t in returns.columns])
        assert p['volatility'] == pytest.approx(np.sqrt(vector @ stock_cov @ vector))


def test_reject_changed_weights_and_missing_or_invalid_prices():
    import json
    raw = json.loads((svc.C.ROOT / svc.ARTIFACT).read_text())
    _, source = bundle()
    wrong = copy.deepcopy(raw); wrong['models'][0]['members'][0]['weight'] += .01
    with pytest.raises(ValueError, match='WEIGHTS_INVALID'): svc.calculate(wrong,source)
    wrong = copy.deepcopy(raw); del wrong['prices']['069500']
    with pytest.raises(KeyError): svc.calculate(wrong,source)
    wrong = copy.deepcopy(raw); wrong['prices']['069500']['prices']['2021-09-01'] = 0
    with pytest.raises(ValueError, match='PRICES_INVALID'): svc.calculate(wrong,source)
