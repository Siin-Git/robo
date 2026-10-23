"""Verification uses isolated test NAVs, never a live database."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from .conftest import register, login
from .test_decisions import confirm, identity
from src.api.services import _common as C, portfolio_service
from src.db.models import Account, NavDaily, PortfolioDecision, PriceDaily


@pytest.fixture
def decision(client, identity, monkeypatch):
    monkeypatch.setattr(C, "now_utc", lambda: datetime(2026, 9, 1, 2, tzinfo=timezone.utc))
    response = confirm(client, identity)
    assert response.status_code == 200, response.text
    return client.get('/api/v1/me/decisions', cookies=identity[0]).json()['items'][0]


def read(client, identity, decision):
    return client.get(f"/api/v1/me/decisions/{decision['decision_id']}/verification", cookies=identity[0])


def navs(env, decision, personal, core):
    start = date.fromisoformat(decision['target_effective_date'])
    with env.factory() as db:
        core_id = db.scalar(select(Account.account_id).where(
            Account.participant_id == decision['participant_id'], Account.account_type == 'core'))
        for aid, points in ((decision['account_id'], personal), (core_id, core)):
            for offset, value, status in points:
                db.add(NavDaily(account_id=aid, date=start + timedelta(days=offset), nav=value,
                    cash_balance=value, nav_base100=100, cumulative_return=0, daily_return=0,
                    stale_price_flag=status == 'STALE_PRICE', nav_status=status,
                    benchmark_version='CORE_V0.3', theme_universe_version='THEME_UNIVERSE_V0.1',
                    risk_model_version='test', execution_rule_version='test'))
        db.commit()


def test_owner_snapshot_read_only_and_summary_binding(client, env, identity, decision, monkeypatch):
    before = read(client, identity, decision).json()
    assert before['actual']['status'] == 'UNAVAILABLE'
    assert before['actual']['personalized_return'] is None
    assert before['original']['personalized']['weights'] == decision['weights']
    assert before['original']['personalized']['expected_return'] == decision['expectations']['expected_return']['value']
    assert before['review']['status'] == 'IN_PROGRESS'
    assert before['review']['automatic_verdict'] is False
    assert client.get('/api/v1/me/portfolio/summary', cookies=identity[0]).json()['decision_id'] == decision['decision_id']
    assert 'internal_tracking' not in str(before) and 'ADMIN_ONLY' not in str(before)
    from src.api.services import frontier_service
    monkeypatch.setattr(frontier_service, 'get_frontier', lambda: {'points': [], 'frontier_version': 'changed'})
    monkeypatch.setattr(portfolio_service, '_expected_return', lambda *args: 999)
    assert read(client, identity, decision).json()['original'] == before['original']
    assert client.get('/api/v1/me/decisions', cookies=identity[0]).json()['items'][0] == decision
    assert client.get(f"/api/v1/me/decisions/{decision['decision_id']}/verification", cookies={}).status_code == 401
    register(client, 'verification-other@example.com')
    other = dict(login(client, 'verification-other@example.com').cookies)
    assert client.get(f"/api/v1/me/decisions/{decision['decision_id']}/verification", cookies=other).status_code == 404


def test_exact_common_dates_exclude_bad_pre_effective_and_future_nav(client, env, identity, decision, monkeypatch):
    start = date.fromisoformat(decision['target_effective_date'])
    monkeypatch.setattr(C, 'now_utc', lambda: datetime.combine(start + timedelta(days=4), datetime.min.time(), timezone.utc))
    navs(env, decision, [(-1, 50, 'OK'), (0, 100, 'OK'), (1, 102, 'OK'), (2, 104, 'OK'), (3, 200, 'STALE_PRICE'), (4, 110, 'OK'), (5, 999, 'OK')],
         [(0, 1000, 'NAV_INCOMPLETE'), (1, 1000, 'OK'), (2, 1010, 'OK'), (3, 1020, 'OK'), (4, 1030, 'OK'), (5, 9999, 'OK')])
    out = read(client, identity, decision).json()
    actual = out['actual']
    assert actual['start'] == (start + timedelta(days=1)).isoformat()
    assert actual['end'] == (start + timedelta(days=4)).isoformat()
    assert actual['observations'] == 3 and actual['excluded_rows'] == 2
    assert actual['personalized_return'] == pytest.approx(110 / 102 - 1)
    assert actual['core_return'] == pytest.approx(.03)
    assert actual['difference_pp'] == pytest.approx(110 / 102 - 1 - .03)
    assert actual['personalized_nav'] == {'start': 102, 'end': 110}
    assert out['review']['status'] == 'IN_PROGRESS'


def test_missing_core_nav_and_one_common_point_never_show_zero_return(client, env, identity, decision, monkeypatch):
    start = date.fromisoformat(decision['target_effective_date'])
    monkeypatch.setattr(C, 'now_utc', lambda: datetime.combine(start + timedelta(days=2), datetime.min.time(), timezone.utc))
    navs(env, decision, [(0, 100, 'OK'), (1, 105, 'OK')], [(1, 1000, 'OK')])
    out = read(client, identity, decision).json()
    assert out['actual']['observations'] == 1
    assert out['actual']['personalized_return'] is None and out['actual']['core_return'] is None


def test_synthetic_and_replay_sources_are_not_forward_performance(client, env, identity, decision, monkeypatch):
    start = date.fromisoformat(decision['target_effective_date'])
    monkeypatch.setattr(C, 'now_utc', lambda: datetime.combine(start + timedelta(days=2), datetime.min.time(), timezone.utc))
    navs(env, decision, [(0, 100, 'OK'), (1, 105, 'OK')], [(0, 1000, 'OK'), (1, 1010, 'OK')])
    from src.api.services import decision_verification_service as svc
    monkeypatch.setattr(svc, 'read_metadata', lambda db: {'start': '2026-01-01'})
    assert read(client, identity, decision).json()['actual']['personalized_return'] is None
    monkeypatch.setattr(svc, 'read_metadata', lambda db: None)
    with env.factory() as db:
        db.add(PriceDaily(asset_id='us_equity', date=start, price=100, source='SYNTHETIC_TEST_VERIFICATION'))
        db.commit()
    actual = read(client, identity, decision).json()['actual']
    assert actual['status'] == 'UNAVAILABLE' and '합성' in actual['reason']


def test_superseded_window_and_missing_original_do_not_backfill(client, env, identity, decision, monkeypatch):
    start = date.fromisoformat(decision['target_effective_date'])
    monkeypatch.setattr(C, 'now_utc', lambda: datetime.combine(start + timedelta(days=10), datetime.min.time(), timezone.utc))
    with env.factory() as db:
        old = db.get(PortfolioDecision, decision['decision_id'])
        values = {column.name: deepcopy(getattr(old, column.name)) for column in PortfolioDecision.__table__.columns}
        values.update(decision_id='legacy-test', version=2, previous_decision_id=old.decision_id,
                      effective_date=start + timedelta(days=1), expectations_json={}, provenance_json={})
        db.add(PortfolioDecision(**values))
        db.commit()
    navs(env, decision, [(0, 100, 'OK'), (1, 105, 'OK')], [(0, 1000, 'OK'), (1, 1010, 'OK')])
    out = read(client, identity, decision).json()
    assert out['superseded_effective_date'] == (start + timedelta(days=1)).isoformat()
    assert out['actual']['observations'] == 1 and out['actual']['personalized_return'] is None
    legacy = read(client, identity, {'decision_id': 'legacy-test'}).json()
    assert legacy['original']['personalized']['expected_return'] is None
    assert legacy['original']['frontier']['points'] == []


def test_summary_does_not_replace_missing_personal_forecast_with_base(client, identity, decision, monkeypatch):
    monkeypatch.setattr(portfolio_service, 'personalized', lambda *args: {
        'weights': [{'asset_id': 'us_equity', 'weight': 1}], 'expected_return': None})
    summary = client.get('/api/v1/me/portfolio/summary', cookies=identity[0]).json()
    assert summary['base']['expected_return'] is not None
    assert summary['personalized']['expected_return'] is None


def test_incomplete_historical_snapshot_stays_readable_without_current_backfill(client, env, identity, decision):
    from src.api.services.internal_tracking_service import SNAPSHOT_KEY
    with env.factory() as db:
        old = db.get(PortfolioDecision, decision['decision_id'])
        values = {column.name: deepcopy(getattr(old, column.name)) for column in PortfolioDecision.__table__.columns}
        values.update(decision_id='incomplete-snapshot', version=2, previous_decision_id=old.decision_id)
        values['provenance_json'] = {
            'base_expectations': {'expected_return': 'missing', 'volatility': 'NaN'},
            SNAPSHOT_KEY: {'frontier': {'points': [
                {'expected_return': .05, 'volatility': .08},
                {'frontier_id': 'bad', 'expected_return': 'missing', 'volatility': .08},
                {'frontier_id': 'negative-risk', 'expected_return': .05, 'volatility': -.08},
                {'frontier_id': 'valid', 'expected_return': '.05', 'volatility': '.08'},
            ]}},
        }
        values['expectations_json'] = {'expected_return': {'value': True}, 'volatility': {'value': 'missing'}}
        db.add(PortfolioDecision(**values))
        db.commit()
    response = read(client, identity, {'decision_id': 'incomplete-snapshot'})
    assert response.status_code == 200
    out = response.json()
    assert out['original']['base']['expected_return'] is None
    assert out['original']['base']['volatility'] is None
    assert out['original']['personalized']['expected_return'] is None
    assert out['original']['personalized']['volatility'] is None
    assert out['original']['frontier']['points'] == [{'frontier_id': 'valid', 'expected_return': .05, 'volatility': .08}]
    assert out['actual']['status'] == 'UNAVAILABLE'
    assert out['actual']['reason'] == '당시 CORE 비교 기준의 버전 미확보'


def test_automatic_reads_follow_new_nav_review_and_job_without_rewriting_decision(client, env, identity, decision, monkeypatch):
    from src.db.models.scheduled_job import ScheduledJob
    start = date.fromisoformat(decision['target_effective_date'])
    due = date.fromisoformat(decision['expectations']['expected_return']['definition']['end'])
    now = datetime.combine(due, datetime.min.time(), timezone.utc)
    monkeypatch.setattr(C, 'now_utc', lambda: now)
    # The annual observation clock also expires the original login session.
    cookies = dict(login(client, 'decision@example.com').cookies)
    identity = cookies, {'X-CSRF-Token': cookies['ra_csrf']}
    initial_response = read(client, identity, decision)
    assert initial_response.status_code == 200, initial_response.text
    initial = initial_response.json()
    assert initial['valuation_job'] is None
    assert initial['review']['status'] == 'IN_PROGRESS'
    navs(env, decision, [(0, 100, 'OK'), ((due-start).days, 104, 'OK')],
         [(0, 1000, 'OK'), ((due-start).days, 1020, 'OK')])
    with env.factory() as db:
        db.add(ScheduledJob(job_id='failed-evaluation', job_type='daily', scheduled_for=due,
            started_at=now, completed_at=now, status='failed', error_message='private diagnostic', stats_json={'private': True}))
        db.commit()
    cookies, headers = identity
    choice = client.post('/api/v1/me/portfolio/choices', cookies=cookies, headers=headers, json={
        'decision_id': decision['decision_id'], 'target_id': decision['target_id'],
        'action': 'KEEP', 'reason': '관측 자료를 확인하고 기존 비중 유지', 'request_key': 'verification-auto-keep'})
    assert choice.status_code == 200, choice.text
    latest = read(client, identity, decision).json()
    assert latest['original'] == initial['original']
    assert latest['actual']['personalized_return'] == pytest.approx(.04)
    assert latest['review']['status'] == 'REVIEW_REQUIRED'
    assert latest['review']['automatic_verdict'] is False
    assert latest['review']['choice']['reason'] == '관측 자료를 확인하고 기존 비중 유지'
    assert latest['valuation_job']['status'] == 'failed'
    assert 'private' not in str(latest)
    assert client.get('/api/v1/me/decisions', cookies=cookies).json()['items'][0] == decision
