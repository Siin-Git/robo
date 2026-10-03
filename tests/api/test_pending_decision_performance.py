"""Regression: a future decision must not hide an active decision's ledger."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from src.api.services import _common as C
from src.db.models import Account, Holding, NavDaily, PriceDaily
from .conftest import login, register


def clock(monkeypatch, day):
    monkeypatch.setattr(C, 'now_utc', lambda: datetime.fromisoformat(day + 'T03:00:00+00:00'))


def add_valuation(session, account_id, day, value):
    session.add(NavDaily(account_id=account_id, date=date.fromisoformat(day), nav=value,
        cash_balance=0, nav_base100=value, daily_return=0, cumulative_return=0,
        nav_status='OK', stale_price_flag=False, benchmark_version='CORE_V0.3',
        theme_universe_version='THEME_UNIVERSE_V0.1', risk_model_version='test', execution_rule_version='test'))
    session.add(Holding(account_id=account_id, date=date.fromisoformat(day), asset_id='us_equity',
        quantity=1, price=value, market_value=value, weight=1))


@pytest.fixture
def timeline(client, env, monkeypatch):
    monkeypatch.setenv('ALLOW_PUBLIC_REGISTRATION', 'true')
    register(client, 'pending-review@example.com')
    cookies = dict(login(client, 'pending-review@example.com').cookies)
    headers = {'X-CSRF-Token': cookies['ra_csrf']}
    frontier = client.get('/api/v1/me/frontier', cookies=cookies).json()
    base = frontier['benchmark_frontier_id']
    clock(monkeypatch, '2026-09-30')
    original = client.post('/api/v1/me/onboarding/complete', cookies=cookies, headers=headers,
        json={'frontier_id': base, 'theme_ids': ['ai'], 'reason': 'original'})
    assert original.status_code == 200, original.text
    original_id = original.json()['decision_id']
    d1 = client.get('/api/v1/me/decisions', cookies=cookies).json()['items'][0]
    assert d1['target_effective_date'] == '2026-10-01'
    with env.factory() as session:
        participant = session.get(Account, d1['account_id']).participant_id
        accounts = session.scalars(select(Account).where(Account.participant_id == participant)).all()
        for a in accounts:
            for day, value in [('2026-10-01', 100), ('2026-10-02', 102)]:
                add_valuation(session, a.account_id, day, value)
        for i, asset in enumerate(sorted(d1['provenance']['base_weights'])):
            if asset == 'cash':
                continue
            for day, value in [('2026-10-01', 100), ('2026-10-02', 100 + 2 * i)]:
                session.add(PriceDaily(asset_id=asset, date=date.fromisoformat(day), price=value, source='SYNTHETIC_TEST'))
        session.commit()
    clock(monkeypatch, '2026-10-03')
    before = client.get('/api/v1/me/performance/dashboard', cookies=cookies).json()
    assert before['observations'] == 2
    alternate = next(p['frontier_id'] for p in frontier['points'] if p['frontier_id'] != base)
    revision = client.post('/api/v1/me/onboarding/complete', cookies=cookies, headers=headers,
        json={'frontier_id': alternate, 'theme_ids': ['semiconductor'], 'reason': 'future revision', 'expected_decision_id': original_id})
    assert revision.status_code == 200, revision.text
    d2 = client.get('/api/v1/me/decisions', cookies=cookies).json()['items'][0]
    assert d2['target_effective_date'] == '2026-10-05'
    assert d1['provenance']['base_weights'] != d2['provenance']['base_weights']
    return cookies, d1, d2, before


def selected_base(report):
    return next(c for c in report['comparators'] if c['key'] == 'selected_base')


def assert_aligned(client, cookies, report):
    contributions = client.get('/api/v1/me/performance/contributions?period=' + report['period'], cookies=cookies).json()
    assert contributions['decision_context'] == report['decision_context']
    assert (contributions['start'], contributions['end'], contributions['observations']) == (
        report['start'], report['end'], report['observations'])
    assert contributions['cumulative_return'] == report['metrics']['cumulative_return']
    for comparison in report['comparators']:
        assert comparison['decision_id'] == report['decision_context']['report_decision_id']
        assert (comparison['start'], comparison['end']) == (report['start'], report['end'])


@pytest.mark.parametrize('period', ['ALL', '1M'])
def test_future_confirmation_retains_active_performance_and_base(client, timeline, period):
    cookies, d1, d2, before = timeline
    after = client.get('/api/v1/me/performance/dashboard?period=' + period, cookies=cookies).json()
    # Exact independent-review reproduction: two observations must remain two.
    assert after['observations'] == 2
    assert after['metrics'] == before['metrics']
    assert selected_base(before)['status'] == selected_base(after)['status'] == 'AVAILABLE'
    expected = sum(w * 2*i/100 for i, (a,w) in enumerate(sorted(d1['provenance']['base_weights'].items())) if a != 'cash')
    assert selected_base(after)['return'] == pytest.approx(expected)
    assert selected_base(after)['return'] == selected_base(before)['return']
    ctx = after['decision_context']
    assert ctx['active_decision']['decision_id'] == d1['decision_id']
    assert ctx['pending_decision']['decision_id'] == d2['decision_id']
    assert ctx['report_decision_id'] == d1['decision_id']
    assert selected_base(after)['decision_id'] == d1['decision_id']
    assert_aligned(client, cookies, after)
    old = client.get(f"/api/v1/me/decisions/{d1['decision_id']}/review", cookies=cookies).json()
    assert old['actual']['observations'] == 2
    assert old['actual']['metrics']['cumulative_return'] == pytest.approx(.02)


@pytest.mark.parametrize('day, count', [('2026-10-04', 0), ('2026-10-04', 2), ('2026-10-05', 0), ('2026-10-05', 1), ('2026-10-06', 2)])
def test_effective_boundary_and_short_new_history(client, env, monkeypatch, timeline, day, count):
    cookies, d1, d2, before = timeline
    with env.factory() as session:
        for offset, value in enumerate([200, 206][:count]):
            add_valuation(session, d2['account_id'], f'2026-10-0{5+offset}', value)
        for i, asset in enumerate(sorted(d2['provenance']['base_weights'])):
            if asset == 'cash':
                continue
            for offset in range(count):
                session.add(PriceDaily(asset_id=asset, date=date(2026, 10, 5+offset), price=100+offset*3*i, source='SYNTHETIC_TEST'))
        session.commit()
    clock(monkeypatch, day)
    report = client.get('/api/v1/me/performance/dashboard', cookies=cookies).json()
    ctx = report['decision_context']
    if day < '2026-10-05':
        assert report['observations'] == 2
        assert ctx['report_decision_id'] == d1['decision_id']
        assert ctx['pending_decision']['decision_id'] == d2['decision_id']
    else:
        assert ctx['active_decision']['decision_id'] == d2['decision_id']
        assert ctx['pending_decision'] is None
        assert ctx['previous_decision']['decision_id'] == d1['decision_id']
        assert report['observations'] == count
        assert report['status'] == ('SHORT_HISTORY' if count == 2 else 'INSUFFICIENT_HISTORY')
        assert report['metrics']['cumulative_return'] == (pytest.approx(.03) if count == 2 else None)
        assert report['metrics']['volatility'] is None
        if count == 2:
            expected = sum(w * 3*i/100 for i, (a,w) in enumerate(sorted(d2['provenance']['base_weights'].items())) if a != 'cash')
            assert selected_base(report)['return'] == pytest.approx(expected)
            assert selected_base(report)['decision_id'] == d2['decision_id']
    assert_aligned(client, cookies, report)
    old = client.get(f"/api/v1/me/decisions/{d1['decision_id']}/review", cookies=cookies).json()
    assert old['actual']['observations'] == 2
    assert old['observation_end'] == '2026-10-02'
    assert all(c['status'] == 'NOT_COMPARABLE' and c['difference'] is None for c in old['comparisons'])


def test_kst_midnight_switch_and_initial_pending(client, env, monkeypatch, timeline):
    cookies, d1, d2, _ = timeline
    for stamp, active in [('2026-10-04T14:59:59+00:00', d1), ('2026-10-04T15:00:00+00:00', d2)]:
        monkeypatch.setattr(C, 'now_utc', lambda: datetime.fromisoformat(stamp))
        report = client.get('/api/v1/me/performance/dashboard', cookies=cookies).json()
        assert report['decision_context']['report_decision_id'] == active['decision_id']
    clock(monkeypatch, '2026-10-03')
    register(client, 'initial-pending@example.com')
    other = dict(login(client, 'initial-pending@example.com').cookies)
    f = client.get('/api/v1/me/frontier', cookies=other).json()
    r = client.post('/api/v1/me/onboarding/complete', cookies=other,
        headers={'X-CSRF-Token':other['ra_csrf']}, json={'frontier_id':f['benchmark_frontier_id'], 'theme_ids':[], 'reason':'first pending'})
    assert r.status_code == 200
    d = client.get('/api/v1/me/decisions', cookies=other).json()['items'][0]
    with env.factory() as session:
        add_valuation(session, d['account_id'], '2026-10-05', 100)
        add_valuation(session, d['account_id'], '2026-10-06', 101)
        session.commit()
    report = client.get('/api/v1/me/performance/dashboard', cookies=other).json()
    assert report['observations'] == 0
    assert report['decision_context']['status'] == 'AWAITING_INITIAL_EFFECTIVE_DATE'
    assert report['decision_context']['report_decision_id'] is None
    assert report['decision_context']['active_decision'] is None
    assert report['decision_context']['pending_decision']['decision_id'] == d['decision_id']
    assert_aligned(client, other, report)
