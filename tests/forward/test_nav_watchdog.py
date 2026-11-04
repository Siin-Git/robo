"""Recovery tests use disposable SQLite/PostgreSQL fixtures and no external prices."""
from datetime import datetime
import json
from pathlib import Path

import pytest
import yaml

from tests.forward.test_competition_start import build
from tests.forward.test_stored_daily import ready, counts, assert_identity, DAY
from src.forward import nav_watchdog as watchdog, run_daily as daily, jobs
from src.forward.competition import KST
from src.forward.runtime import get_database_path


def prepared(build, monkeypatch, number=2, prices=True):
    x = ready(build, number, with_prices=prices)
    # Isolated observed-price stand-in, never loaded into production.
    x.con.execute("UPDATE prices_daily SET source='ISOLATED_OBSERVED_TEST'")
    x.con.commit()
    x.clock['now'] = datetime(2026, 10, 7, 18, 43, tzinfo=KST)
    monkeypatch.setattr('src.forward.runtime.kst_today', lambda: x.clock['now'].date())
    return x


def recover(x, collector=lambda: 0, repair=True):
    return watchdog.recover(x.con, x.cfg, get_database_path(), now=x.clock['now'], repair=repair,
                            collect=collector, evaluate=lambda: daily.main(['--use-stored-prices', '--missing-nav-only']))


def rows(con, table):
    return sorted([tuple(r) for r in con.execute('SELECT * FROM '+table).fetchall()], key=str)


def test_server_recovery_writes_real_evidence_for_all_30_and_then_does_nothing(build, monkeypatch):
    x = prepared(build, monkeypatch, 15)
    assert watchdog.audit(x.con, x.cfg, DAY)['state'] == 'NAV_MISSING'
    report = recover(x)
    assert report['state'] == 'NAV_COMPLETE', report
    assert report['after']['normal_accounts'] == 30
    assert report['after']['personalized'] == report['after']['core'] == report['after']['complete_pairs'] == 15
    saved = {t: rows(x.con, t) for t in ['orders','trades','holdings_daily','nav_daily','events','scheduled_jobs']}
    assert recover(x)['state'] == 'NAV_COMPLETE'
    assert {t: rows(x.con, t) for t in saved} == saved
    assert_identity(x)


def test_partial_account_failure_retries_only_missing_nav_without_rewriting_completed_accounts(build, monkeypatch):
    x = prepared(build, monkeypatch)
    aid = x.con.execute('SELECT account_id FROM accounts ORDER BY account_id LIMIT 1').fetchone()[0]
    original = daily.valuate
    with monkeypatch.context() as patch:
        def fail(con, account, *args):
            if account == aid:
                raise RuntimeError('isolated valuation failure')
            return original(con, account, *args)
        patch.setattr(daily, 'valuate', fail)
        assert recover(x)['state'] == 'NAV_MISSING'
    saved = {t: [r for r in rows(x.con,t) if aid not in r and (t != 'events' or r[3] is not None)] for t in ['orders','trades','holdings_daily','nav_daily','events']}
    assert recover(x)['state'] == 'WINDOW_ALREADY_ATTEMPTED'
    x.clock['now'] = x.clock['now'].replace(hour=20)
    report = recover(x)
    assert report['state'] == 'NAV_COMPLETE', report
    assert {t: [r for r in rows(x.con,t) if aid not in r and (t != 'events' or r[3] is not None)] for t in saved} == saved
    assert not x.con.execute('SELECT order_id FROM trades GROUP BY order_id HAVING COUNT(*)>1').fetchall()
    assert_identity(x)


def test_three_windows_bound_attempts_and_missing_prices_do_not_create_orders(build, monkeypatch):
    x = prepared(build, monkeypatch, prices=False)
    called = []
    for hour in (18,20,22):
        x.clock['now'] = x.clock['now'].replace(hour=hour)
        assert recover(x, lambda: called.append(hour) or 0)['state'] == 'PRICE_WAIT'
        for _ in range(3):
            assert recover(x)['state'] == 'WINDOW_ALREADY_ATTEMPTED'
    assert called == [18,20,22]
    assert counts(x.con) == dict.fromkeys(counts(x.con),0)
    assert x.con.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE status='success'").fetchone()[0] == 3


def test_prices_arrive_then_same_day_recovery_finishes(build, monkeypatch):
    x = prepared(build, monkeypatch, prices=False)
    assert recover(x)['state'] == 'PRICE_WAIT'
    x.clock['now'] = x.clock['now'].replace(hour=20)
    def collector():
        x.prices(DAY)
        x.con.execute("UPDATE prices_daily SET source='ISOLATED_OBSERVED_TEST'")
        x.con.commit()
        return 0
    assert recover(x, collector)['state'] == 'NAV_COMPLETE'


@pytest.mark.parametrize('condition', ['read_only','before_window','weekend','daily_running','watchdog_running','consumed_success'])
def test_no_recovery_writes_when_not_safe(build, monkeypatch, condition):
    x = prepared(build, monkeypatch)
    expected = {'read_only':'NAV_MISSING','before_window':'OUTSIDE_RECOVERY_WINDOW','weekend':'OUTSIDE_RECOVERY_WINDOW',
                'daily_running':'RUNNING','watchdog_running':'RECOVERY_RUNNING','consumed_success':'JOB_NAV_MISMATCH'}[condition]
    if condition in {'daily_running','watchdog_running','consumed_success'}:
        typ = 'navcheck-18' if condition == 'watchdog_running' else 'daily'
        jid, _ = jobs.claim_job(None, typ, DAY, sqlite_path=get_database_path())
        if condition == 'consumed_success':
            jobs.complete_job(None, jid, {'status':'PASS','outcome':'SUCCESS','valuated':4}, sqlite_path=get_database_path())
    if condition == 'before_window': x.clock['now'] = x.clock['now'].replace(hour=17)
    if condition == 'weekend': x.clock['now'] = x.clock['now'].replace(day=10)
    before = {t:rows(x.con,t) for t in ['orders','trades','nav_daily','events','scheduled_jobs']}
    def forbidden(): pytest.fail('must not fetch prices or evaluate')
    result = watchdog.recover(x.con,x.cfg,get_database_path(),now=x.clock['now'],repair=condition!='read_only',collect=forbidden,evaluate=forbidden)
    assert result['state'] == expected
    assert {t:rows(x.con,t) for t in before} == before


@pytest.mark.parametrize('kind', ['synthetic','replay','nav_history'])
def test_unverified_sources_are_never_promoted_to_operating_nav(build, monkeypatch, kind):
    x = prepared(build, monkeypatch)
    if kind == 'synthetic': x.con.execute("UPDATE prices_daily SET source='SYNTHETIC_TEST'")
    elif kind == 'replay': x.con.execute("INSERT INTO forward_state (key,value,updated_at) VALUES ('replay_run_id','fixture','2026-10-07')")
    else:
        aid = x.con.execute('SELECT account_id FROM accounts LIMIT 1').fetchone()[0]
        from src.forward.db import log_event
        log_event(x.con,'NAV_CALCULATED','test',account_id=aid,payload={'date':'2026-10-01','data_kind':'HISTORICAL_REPLAY'})
    x.con.commit()
    assert recover(x)['state'] == 'UNVERIFIED_DATA'
    assert counts(x.con)['nav_daily'] == 0


def test_collector_exception_is_sanitized_and_consumes_window(build, monkeypatch):
    x = prepared(build, monkeypatch)
    def fail(): raise RuntimeError('SECRET_MUST_NOT_LEAK')
    report = recover(x, fail)
    assert report['state'] == 'RECOVERY_ERROR'
    assert 'SECRET' not in json.dumps(report)
    assert recover(x)['state'] == 'WINDOW_ALREADY_ATTEMPTED'
    assert not any(counts(x.con).values())


def test_collector_failure_does_not_evaluate_even_with_prices(build, monkeypatch):
    x = prepared(build, monkeypatch)
    assert recover(x,lambda:1)['state'] == 'PRICE_COLLECTION_FAILED'
    assert not any(counts(x.con).values())


@pytest.mark.parametrize('fault', ['provenance','cash','pending','stale'])
def test_inconsistent_existing_nav_is_reported_not_overwritten(build, monkeypatch, fault):
    x = prepared(build, monkeypatch)
    assert recover(x)['state'] == 'NAV_COMPLETE'
    if fault == 'provenance': x.con.execute("DELETE FROM events WHERE event_type='NAV_CALCULATED'")
    if fault == 'cash': x.con.execute('UPDATE nav_daily SET cash_balance=cash_balance+1000')
    if fault == 'stale': x.con.execute('UPDATE nav_daily SET stale_price_flag=?',(True,))
    if fault == 'pending': x.con.execute("UPDATE orders SET status='pending'")
    x.con.commit()
    before = rows(x.con,'nav_daily')
    assert recover(x)['state'] == 'NAV_REVIEW_REQUIRED'
    assert rows(x.con,'nav_daily') == before


def test_start_policy_is_not_changed_by_watchdog(build,monkeypatch):
    x = prepared(build,monkeypatch)
    x.clock['now'] = x.clock['now'].replace(day=6)
    assert recover(x)['state'] == 'POLICY_BLOCKED'
    assert not any(counts(x.con).values())


def test_workflow_shares_financial_queue_and_requires_explicit_repair():
    flow=yaml.safe_load(Path('.github/workflows/nav_watchdog.yml').read_text())
    assert flow['concurrency']=={'group':'forward-jobs','cancel-in-progress':False}
    triggers=flow.get('on',flow.get(True))
    assert triggers['schedule']==[{'cron':'43 9,11,13 * * 1-5'}]
    assert triggers['workflow_dispatch']['inputs']['repair']['default'] is False
    job=flow['jobs']['verify-and-recover']
    assert 'release/public-operation' in job['if']
    step=next(s for s in job['steps'] if s.get('name')=='Verify actual NAV and recover safely')
    assert '--repair' in step['run'] and 'FORWARD_DAILY_ENABLED' in step['env']
    assert '--force' not in str(flow) and '--scheduled-for' not in str(flow)
    assert flow['permissions']=={'contents':'read'}
    assert job['steps'][-1]['if']=='${{ always() }}'


def test_concurrent_watchdogs_do_not_overlap_recovery(build, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import sqlite3
    x = prepared(build, monkeypatch)
    entered, release = Event(), Event()
    def collector():
        entered.set()
        assert release.wait(15)
        return 0
    def worker():
        con = x.reopen()
        con.row_factory = sqlite3.Row
        try:
            return watchdog.recover(con,x.cfg,get_database_path(),now=x.clock['now'],repair=True,
                                    collect=collector,evaluate=lambda:daily.main(['--use-stored-prices','--missing-nav-only']))
        finally:
            con.close()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        try:
            assert entered.wait(15)
            assert recover(x)['state'] == 'RECOVERY_RUNNING'
        finally:
            release.set()
        assert future.result(timeout=30)['state'] == 'NAV_COMPLETE'
    assert x.con.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE job_type=?",('navcheck-18',)).fetchone()[0] == 1
    assert not x.con.execute('SELECT order_id FROM trades GROUP BY order_id HAVING COUNT(*)>1').fetchall()


def test_recovery_cli_cannot_bypass_slot_or_rewrite_a_past_date(build,monkeypatch):
    x = prepared(build,monkeypatch)
    assert daily.main(['--use-stored-prices','--missing-nav-only','--scheduled-for','2026-10-06']) == 2
    assert not any(counts(x.con).values())
    assert x.con.execute('SELECT COUNT(*) FROM scheduled_jobs').fetchone()[0] == 0


def test_watchdog_fails_closed_without_explicit_operating_configuration(monkeypatch,tmp_path):
    monkeypatch.setenv('FORWARD_DAILY_ENABLED','false')
    monkeypatch.setattr('src.forward.run_prices.operating_store',lambda **kw:pytest.fail('must not connect'))
    output=tmp_path/'report.json'
    assert watchdog.main(['--repair','--output',str(output)]) == 1
    assert json.loads(output.read_text()) == {'state':'CHECK_FAILED','error_type':'ValueError','repair_requested':True}


def test_recovery_preserves_inherited_replay_opening_without_second_initial_buy(build,monkeypatch):
    from tests.forward.test_replay_handoff import prepare
    from src.forward.handoff import apply,digest
    x,plan=prepare(build)
    apply(x.con,plan,digest(plan))
    x.prices(DAY)
    x.con.execute("UPDATE prices_daily SET source='ISOLATED_OBSERVED_TEST'")
    x.con.commit()
    x.clock['now']=datetime(2026,10,7,18,43,tzinfo=KST)
    monkeypatch.setattr('src.forward.runtime.kst_today',lambda:x.clock['now'].date())
    original_decisions=rows(x.con,'portfolio_decisions')
    report=recover(x)
    assert report['state']=='NAV_COMPLETE',report
    assert report['after']['complete_pairs']==15
    assert x.con.execute('SELECT COUNT(*) FROM trades').fetchone()[0]==0
    assert rows(x.con,'portfolio_decisions')==original_decisions
    assert_identity(x)


def test_abandoned_running_job_stays_locked_but_is_not_reported_healthy(build,monkeypatch):
    x=prepared(build,monkeypatch)
    jid,_=jobs.claim_job(None,'daily',DAY,sqlite_path=get_database_path())
    x.con.execute('UPDATE scheduled_jobs SET started_at=? WHERE job_id=?',('2026-01-01T00:00:00+00:00',jid))
    x.con.commit()
    assert recover(x)['state']=='RUNNING_REVIEW_REQUIRED'
    assert x.con.execute('SELECT status FROM scheduled_jobs WHERE job_id=?',(jid,)).fetchone()[0]=='running'
    assert not any(counts(x.con).values())
