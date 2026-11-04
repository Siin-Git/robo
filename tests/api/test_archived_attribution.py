"""Archived attribution uses the saved owner ledger, without live writes."""
from copy import deepcopy
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, func
from src.db.models import Event, NavDaily, Trade
from .test_ledger_comparison import confirmed


def test_history_attribution_reconciles_trading_cost_and_preserves_archive(client, env, monkeypatch):
    cookies, decision = confirmed(client, monkeypatch, 'attribution-owner@example.com')
    other, _ = confirmed(client, monkeypatch, 'attribution-other@example.com')
    days = ['2026-10-02', '2026-10-06', '2026-10-09']
    payload = {
        'kind': 'HISTORICAL_REPLAY', 'decision_id': decision['decision_id'],
        'series': [{'date': d, 'core_nav': b} for d, b in zip(days, [100, 101, 102])],
        'ledger': {
            'snapshots': [{'date': d, 'nav': nav, 'cash_balance': cash, 'nav_status': 'OK',
                'holdings': [{'asset_id': 'us_equity', 'market_value': value, 'price': value}]}
                for d, nav, cash, value in zip(days, [100, 108, 118], [20, 9, 9], [80, 99, 109])],
            'trades': [{'execution_at': '2026-10-06T09:00:00', 'asset_id': 'us_equity',
                'quantity': 1, 'gross_value': 10, 'transaction_cost': 1}],
        },
    }
    original = deepcopy(payload)
    with env.factory() as db:
        db.add(Event(event_id='attribution-archive', event_type='HISTORICAL_REPLAY_ARCHIVED',
            account_id=decision['account_id'], participant_id=decision['participant_id'],
            timestamp=datetime.now(timezone.utc), model_version='test', payload_json=payload))
        db.commit()
        counts = tuple(db.scalar(select(func.count()).select_from(model)) for model in (NavDaily, Trade))
    response = client.get('/api/v1/me/performance/history', cookies=cookies)
    assert response.status_code == 200
    report = response.json()['report']['performance_report']
    assets = {a['asset_id']: a['contribution'] for a in report['assets']}
    assert report['metrics']['cumulative_return'] == pytest.approx(.18)
    assert assets['us_equity'] == pytest.approx(.19)
    assert assets['costs'] == pytest.approx(-.01)
    assert assets['unexplained'] == pytest.approx(0)
    for point in report['attribution']:
        assert sum(point['values'].values()) == pytest.approx(point['total'])
    assert client.get('/api/v1/me/performance/history', cookies=other).json() == {'available': False}
    with env.factory() as db:
        assert db.get(Event, 'attribution-archive').payload_json == original
        assert counts == tuple(db.scalar(select(func.count()).select_from(model)) for model in (NavDaily, Trade))
