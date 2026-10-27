"""Verification uses isolated test NAVs, never a live database."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

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
    assert before['risk_change']['status'] == 'UNAVAILABLE'
    assert before['risk_change']['difference_pp'] is None
    assert before['review_plan']['basis_date'] == decision['target_effective_date']
    assert [item['months'] for item in before['review_plan']['checkpoints']] == [3, 6]
    assert all(item['state'] == 'UPCOMING' for item in before['review_plan']['checkpoints'])
    assert client.get('/api/v1/me/portfolio/summary', cookies=identity[0]).json()['decision_id'] == decision['decision_id']
    assert 'internal_tracking' not in str(before) and 'ADMIN_ONLY' not in str(before)
    from src.api.services import frontier_service
    monkeypatch.setattr(frontier_service, 'get_frontier', lambda: {'points': [], 'frontier_version': 'changed'})
    monkeypatch.setattr(portfolio_service, '_expected_return', lambda *args: 999)
    assert read(client, identity, decision).json()['original'] == before['original']
    assert read(client, identity, decision).json()['risk_change'] == before['risk_change']
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
    assert out['risk_change']['status'] == 'UNAVAILABLE'


def test_saved_risk_pair_requires_both_values_method_and_date(client, env, identity, decision):
    with env.factory() as db:
        old = db.get(PortfolioDecision, decision['decision_id'])
        values = {column.name: deepcopy(getattr(old, column.name)) for column in PortfolioDecision.__table__.columns}
        values.update(decision_id='risk-missing', version=2, previous_decision_id=old.decision_id)
        values['provenance_json'] = {**values['provenance_json'], 'risk_comparison': {
            'base_volatility': .08, 'personalized_volatility': .09, 'method': None, 'as_of': '2026-09-01'}}
        values['expectations_json'] = {**values['expectations_json'], 'volatility': {'value': .09}}
        db.add(PortfolioDecision(**values))
        db.commit()
    result = read(client, identity, {'decision_id': 'risk-missing'}).json()
    assert result['original']['personalized']['volatility'] is not None
    assert result['risk_change']['status'] == 'UNAVAILABLE'
    assert result['risk_change']['difference_pp'] is None


def test_saved_same_model_risk_pair_is_read_without_recomputing(client, env, identity, decision, monkeypatch):
    with env.factory() as db:
        old = db.get(PortfolioDecision, decision['decision_id'])
        values = {column.name: deepcopy(getattr(old, column.name)) for column in PortfolioDecision.__table__.columns}
        values.update(decision_id='risk-recorded', version=2, previous_decision_id=old.decision_id)
        values['provenance_json'] = {**values['provenance_json'], 'risk_comparison': {
            'base_volatility': .08, 'personalized_volatility': .09,
            'method': '5Y weekly Ledoit-Wolf', 'as_of': '2026-08-31'}}
        db.add(PortfolioDecision(**values))
        db.commit()
    monkeypatch.setattr(portfolio_service, '_cov_asof', lambda *args: (_ for _ in ()).throw(AssertionError('recomputed')))
    result = read(client, identity, {'decision_id': 'risk-recorded'}).json()
    assert result['risk_change'] == {'status': 'AVAILABLE', 'base_volatility': .08,
        'personalized_volatility': .09, 'difference_pp': pytest.approx(1),
        'as_of': '2026-08-31', 'method': '5Y weekly Ledoit-Wolf'}


def test_review_dates_use_forward_start_and_never_claim_observation_early():
    from src.api.services.decision_verification_service import _add_months, _review_plan
    assert _add_months(date(2027, 1, 31), 1) == date(2027, 2, 28)
    start, forward = date(2026, 10, 13), date(2026, 10, 26)
    unavailable = {'end': None}
    waiting = _review_plan(start, forward, date(2027, 1, 26), unavailable, [], None)
    assert waiting['basis_date'] == '2026-10-26'
    assert waiting['checkpoints'] == [
        {'months': 3, 'date': '2027-01-26', 'state': 'DATA_PENDING'},
        {'months': 6, 'date': '2027-04-26', 'state': 'UPCOMING'}]
    observed = _review_plan(start, forward, date(2027, 1, 27), {'end': '2027-01-26'}, [], None)
    assert observed['checkpoints'][0]['state'] == 'DUE'
    choice = SimpleNamespace(selected_at=datetime(2027, 1, 27, tzinfo=timezone.utc))
    reviewed = _review_plan(start, forward, date(2027, 1, 28), {'end': '2027-01-26'}, [choice], None)
    assert reviewed['checkpoints'][0]['state'] == 'RECORDED'
    later = SimpleNamespace(selected_at=datetime(2027, 4, 27, tzinfo=timezone.utc))
    both = _review_plan(start, forward, date(2027, 4, 28), {'end': '2027-04-26'}, [later, choice], None)
    assert [item['state'] for item in both['checkpoints']] == ['RECORDED', 'RECORDED']
    ended = _review_plan(start, forward, date(2027, 1, 28), unavailable, [], date(2027, 1, 20))
    assert all(item['state'] == 'ENDED' for item in ended['checkpoints'])


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


@pytest.mark.parametrize('job_status,stats,state', [
    ('success', {'status':'COMPETITION_WAIT', 'reason':'START_NOT_SCHEDULED', 'ready':15, 'required':15, 'valuated':0}, 'START_WAIT'),
    ('skipped', {'status':'COMPETITION_WAIT', 'reason':'AWAITING_T0'}, 'START_WAIT'),
    ('success', {'status':'COMPETITION_WAIT', 'reason':'PARTICIPANTS_NOT_READY', 'ready':14, 'required':15}, 'PARTICIPANTS_NOT_READY'),
    ('success', {'status':'PARTIAL', 'valuated':2}, 'PARTIAL'),
    ('success', {'status':'PASS', 'valuated':0}, 'NO_NAV'),
    ('success', {}, 'UNKNOWN'),
    ('running', {}, 'RUNNING'),
    ('failed', {'status':'FAIL', 'outcome':'PARTIAL', 'valuated':1}, 'EVALUATION_FAILED'),
    ('success', {'status':'PARTIAL', 'valuated':5, 'account_results':{'private-account':{'status':'NAV_INCOMPLETE', 'reason':'no executions yet'}}}, 'PRICE_WAIT'),
    ('skipped', {'status':'PARTIAL', 'price_wait_accounts':['private-account'], 'valuated':0}, 'PRICE_WAIT'),
    ('success', {'status':'COMPETITION_WAIT', 'reason':'postgres://private-secret'}, 'OPERATION_WAIT'),
])
def test_execution_status_is_not_valuation_completion(client, env, identity, decision, job_status, stats, state):
    from src.db.models.scheduled_job import ScheduledJob
    with env.factory() as db:
        db.add(ScheduledJob(job_id='outcome', job_type='daily', scheduled_for=date(2026,9,2),
            started_at=C.now_utc(), completed_at=C.now_utc(), status=job_status,
            error_message='private-secret', stats_json={**stats, 'diagnostic':'private-secret'}))
        db.commit()
    out = read(client, identity, decision).json()
    job = out['valuation_job']
    assert job['state'] == state
    assert not job['valuation_completed']
    assert job['execution_succeeded'] == (job_status == 'success')
    assert job['reason_code'] == (stats.get('reason') if stats.get('reason') in {'START_NOT_SCHEDULED','AWAITING_T0','PARTICIPANTS_NOT_READY'} else None)
    assert 'private-' not in str(out)
    assert 'stats_json' not in str(out)
    assert out['actual']['personalized_return'] is None


def test_completed_job_needs_persisted_nav_and_duplicate_skip_preserves_evidence(client, env, identity, decision):
    from src.db.models.scheduled_job import ScheduledJob
    start = date.fromisoformat(decision['target_effective_date'])
    with env.factory() as db:
        db.add(ScheduledJob(job_id='completed', job_type='daily', scheduled_for=start,
            started_at=C.now_utc(), completed_at=C.now_utc(), status='success',
            stats_json={'status':'PASS','outcome':'SUCCESS','valuated':2,'asof':str(start)}))
        db.commit()
    assert read(client, identity, decision).json()['valuation_job']['state'] == 'PARTIAL'
    navs(env, decision, [(0,100,'OK')], [(0,1000,'OK')])
    with env.factory() as db:
        db.add(ScheduledJob(job_id='duplicate', job_type='daily', scheduled_for=start,
            started_at=C.now_utc()+timedelta(seconds=1), completed_at=C.now_utc(), status='skipped', stats_json={}))
        db.commit()
    job = read(client, identity, decision).json()['valuation_job']
    assert job['state'] == 'NAV_COMPLETE' and job['valuation_completed']
    assert job['latest_attempt_status'] == 'skipped' and job['status'] == 'success'
    with env.factory() as db:
        row = db.scalar(select(NavDaily).where(NavDaily.account_id == decision['account_id']))
        row.nav_status = 'STALE_PRICE'
        db.commit()
    assert not read(client, identity, decision).json()['valuation_job']['valuation_completed']


@pytest.mark.parametrize('source', ['synthetic', 'Synthetic_fixture', 'SYNTHETIC_TEST'])
def test_all_known_synthetic_labels_are_rejected(client, env, identity, decision, source):
    with env.factory() as db:
        db.add(PriceDaily(asset_id='us_equity', date=date(2026,9,2), price=100, source=source))
        db.commit()
    assert '합성' in read(client, identity, decision).json()['actual']['reason']


def test_copied_replay_metadata_and_read_purity(client, env, identity, decision, monkeypatch):
    from src.db.models.operational import ForwardState
    from src.forward import run_daily, execution, ledger
    from sqlalchemy import text
    with env.factory() as db:
        db.add(ForwardState(key='replay_run_id', value='copied-replay', updated_at=C.now_utc()))
        db.commit()
    def forbidden(*args, **kwargs):
        pytest.fail('GET must not execute financial work')
    monkeypatch.setattr(run_daily, '_execute_daily', forbidden)
    monkeypatch.setattr(execution, 'create_orders', forbidden)
    monkeypatch.setattr(ledger, 'valuate', forbidden)
    tables = ('orders','trades','nav_daily','holdings_daily','scheduled_jobs','portfolio_decisions','portfolio_choices','events')
    def counts():
        with env.factory() as db:
            return [db.scalar(text('SELECT COUNT(*) FROM '+t)) for t in tables]
    before = counts()
    out = read(client, identity, decision).json()
    assert '재생' in out['actual']['reason']
    assert counts() == before


def test_core_version_mismatch_cannot_be_used(client, env, identity, decision, monkeypatch):
    start = date.fromisoformat(decision['target_effective_date'])
    monkeypatch.setattr(C,'now_utc',lambda: datetime.combine(start+timedelta(days=2),datetime.min.time(),timezone.utc))
    navs(env, decision, [(0,100,'OK'),(1,105,'OK')], [(0,1000,'OK'),(1,1010,'OK')])
    with env.factory() as db:
        for row in db.scalars(select(NavDaily).where(NavDaily.account_id != decision['account_id'])):
            row.benchmark_version = 'OTHER_CORE'
        db.commit()
    actual = read(client, identity, decision).json()['actual']
    assert actual['status'] == 'UNAVAILABLE' and actual['observations'] == 0


def test_job_date_is_not_valuation_date_and_stale_counts_are_not_normal(client, env, identity, decision):
    from src.db.models.scheduled_job import ScheduledJob
    start = date.fromisoformat(decision['target_effective_date'])
    navs(env, decision, [(0,100,'STALE_PRICE')], [(0,1000,'OK')])
    with env.factory() as db:
        accounts = list(db.scalars(select(NavDaily.account_id)))
        db.add(ScheduledJob(job_id='price-wait-date', job_type='daily', scheduled_for=start+timedelta(days=1),
            started_at=C.now_utc(), completed_at=C.now_utc(), status='success', stats_json={
                'asof':str(start), 'status':'PASS', 'valuated':30,
                'account_results':{aid:{'status':'STALE_PRICE'} for aid in accounts}}))
        db.commit()
    job = read(client, identity, decision).json()['valuation_job']
    assert job['scheduled_for'] == str(start+timedelta(days=1))
    assert job['valuation_date'] == str(start)
    assert (job['normal_nav_accounts'],job['stale_nav_accounts'],job['expected_nav_accounts']) == (1,1,2)
    assert job['state'] == 'PRICE_WAIT' and not job['valuation_completed']
    assert not any(aid in str(job) for aid in accounts)


@pytest.mark.parametrize('asof', [None,'invalid','2026-99-99'])
def test_missing_valuation_date_never_uses_scheduled_date_or_legacy_counter(client, env, identity, decision, asof):
    from src.db.models.scheduled_job import ScheduledJob
    start = date.fromisoformat(decision['target_effective_date'])
    navs(env, decision, [(0,100,'OK')], [(0,1000,'OK')])
    with env.factory() as db:
        db.add(ScheduledJob(job_id='unknown-date', job_type='daily', scheduled_for=start,
            started_at=C.now_utc(), status='success', stats_json={'asof':asof,'status':'PASS','valuated':30}))
        db.commit()
    job = read(client, identity, decision).json()['valuation_job']
    assert job['valuation_date'] is None
    assert job['normal_nav_accounts'] is None and job['stale_nav_accounts'] is None
    assert not job['valuation_completed']


def test_persisted_counts_exclude_accounts_outside_job_and_preserve_zero(client, env, identity, decision):
    from src.db.models.scheduled_job import ScheduledJob
    start = date.fromisoformat(decision['target_effective_date'])
    navs(env, decision, [(0,100,'NAV_INCOMPLETE')], [(0,1000,'OK')])
    with env.factory() as db:
        db.add(ScheduledJob(job_id='scope', job_type='daily', scheduled_for=start,
            started_at=C.now_utc(), status='success', stats_json={'asof':str(start),'status':'PASS',
                'valuated':1,'account_results':{decision['account_id']:{'status':'OK'}}}))
        db.commit()
    job = read(client, identity, decision).json()['valuation_job']
    assert (job['normal_nav_accounts'],job['stale_nav_accounts'],job['expected_nav_accounts']) == (0,0,1)
    assert job['state'] == 'PARTIAL' and not job['valuation_completed']


def test_legacy_job_without_account_list_does_not_claim_scoped_counts(client, env, identity, decision):
    from src.db.models.scheduled_job import ScheduledJob
    start = date.fromisoformat(decision['target_effective_date'])
    navs(env, decision, [(0,100,'OK')], [(0,1000,'OK')])
    with env.factory() as db:
        db.add(ScheduledJob(job_id='legacy-scope', job_type='daily', scheduled_for=start,
            started_at=C.now_utc(), status='success', stats_json={'asof':str(start),'status':'PASS','valuated':2}))
        db.commit()
    job = read(client, identity, decision).json()['valuation_job']
    assert job['valuation_date'] == str(start)
    assert job['normal_nav_accounts'] is None and job['expected_nav_accounts'] is None
