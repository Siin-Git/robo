"""Read-only snapshot-composition estimates; no account or PriceDaily writes."""
from functools import lru_cache
from hashlib import sha256
import json
import math

import numpy as np
import pandas as pd
from src.portfolio.optimizer import portfolio_stats
from src.risk.covariance import ledoit_wolf_covariance, annualize_covariance
from . import _common as C
from .strategy_service import bundle

ARTIFACT = 'data/strategy_research/composition_prices_20261013.json'


def calculate(data, source):
    models = data['models']
    if {m['id'] for m in models} != {'leader_stock', 'export_stock'} or len(models) != 2:
        raise ValueError('STRATEGY_IDS_INVALID')
    original = source['snapshots']
    leader = original['leader_measurement']
    export = original['export_historical']['items'][-1]
    weights_expected = {
        'leader_stock': {m['ticker'].removeprefix('A'): m['weight'] for m in leader['members']},
        'export_stock': {**{m['ticker']: m['actual_weight'] for m in export['members'] if m['actual_weight'] > 0}, 'cash': export['cash_weight']}}
    symbols = sorted({t for w in weights_expected.values() for t in w if t != 'cash'})
    weekly = {}
    for ticker in symbols:
        observed = data['prices'][ticker]
        if observed['session_timezone'] != 'Asia/Seoul' or observed['symbol'].split('.')[0] != ticker:
            raise ValueError('STRATEGY_SYMBOL_INVALID')
        levels = pd.Series(observed['prices'], dtype=float)
        levels.index = pd.to_datetime(levels.index)
        if not levels.index.is_monotonic_increasing or levels.index.has_duplicates or not np.isfinite(levels).all() or (levels <= 0).any():
            raise ValueError('STRATEGY_PRICES_INVALID')
        # Compute before joining: never bridge a missing week or interpolate prices.
        weekly[ticker] = levels.resample('W-FRI').last().pct_change(fill_method=None)
    returns = pd.DataFrame(weekly).dropna(how='any')
    if len(returns) < 52:
        raise ValueError('STRATEGY_COMMON_HISTORY_INSUFFICIENT')
    # Shrink observed stock covariance before adding deterministic zero-risk cash.
    cov = annualize_covariance(ledoit_wolf_covariance(returns), 52)
    returns['cash'] = 0.0
    order = list(returns.columns)
    mu = returns.mean() * 52
    cov = cov.reindex(index=order, columns=order, fill_value=0.0)
    result = []
    for model in models:
        weights = {m['ticker']: float(m['weight']) for m in model['members']}
        expected = weights_expected[model['id']]
        if set(weights) != set(expected) or any(abs(weights[k]-expected[k]) > 1e-12 for k in expected) or not math.isclose(sum(weights.values()), 1, abs_tol=1e-8):
            raise ValueError('STRATEGY_SNAPSHOT_WEIGHTS_INVALID')
        vector = np.array([weights.get(t, 0) for t in order])
        ret, vol, sharpe = portfolio_stats(vector, mu.to_numpy(), cov.to_numpy(), .03)
        if not all(math.isfinite(v) for v in (ret, vol, sharpe)):
            raise ValueError('STRATEGY_ESTIMATE_INVALID')
        result.append({'id': model['id'], 'label': model['label'], 'expected_return': ret,
            'volatility': vol, 'sharpe': sharpe, 'risk_free_rate': .03,
            'snapshot_date': model['as_of'], 'weights': model['members'], 'source_file': model['source']})
    return {'version':data['version'], 'data_kind':'HISTORICAL_COMPOSITION_ESTIMATE',
        'return_basis':'WEIGHTED_WEEKLY_ARITHMETIC_MEAN_ANNUALIZED_52',
        'risk_basis':'COMMON_WEEKLY_LEDOIT_WOLF_ANNUALIZED_52',
        'period':{'start':str(returns.index[0].date()),'end':str(returns.index[-1].date()),'observations':len(returns)},
        'actual_account_history':False, 'confirmation_eligible':False,
        'note':'제공된 종목·비중을 공통 기간의 과거 가격에 적용한 추정치입니다. 기본 Frontier의 BL 기대수익률과 계산 기준이 달라 우열을 뜻하지 않습니다. 현금 수익·거래 비용은 제외합니다.',
        'items':result}


@lru_cache(maxsize=1)
def comparison():
    raw = (C.ROOT / ARTIFACT).read_bytes()
    _, source = bundle()
    result = calculate(json.loads(raw), source)
    result['artifact_sha256'] = sha256(raw).hexdigest()
    return result
