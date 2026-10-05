"""Daily execution against disposable SQLite/PostgreSQL, never market/network data."""
from datetime import datetime
from pathlib import Path
import json

import pytest
import yaml

from tests.forward.test_competition_start import build  # parametrized isolated DB fixture
from src.forward import competition
from src.forward import run_daily as daily
from src.forward.accounts import versions_from_cfg
from src.forward.execution import create_orders

DAY = '2026-10-07'
TABLES = ('orders', 'trades', 'holdings_daily', 'nav_daily')


def ready(build, number=2, with_prices=True):
    x = build(number)
    for i in range(number):
        x.confirm(i)
    competition.schedule_start(x.con, DAY)
    x.clock['now'] = datetime(2026, 10, 7, 17, 17, tzinfo=competition.KST)
    if with_prices:
        x.prices(DAY)
    return x


def run(x):
    return daily._execute_daily(x.con, x.cfg, DAY, use_stored_prices=True)


def counts(con):
    return {table: con.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in TABLES}


def account_ids(x):
    return [r['account_id'] for r in x.con.execute('SELECT account_id FROM accounts ORDER BY account_id').fetchall()]


def assert_identity(x):
    for row in x.con.execute('SELECT * FROM nav_daily').fetchall():
        mv = x.con.execute('SELECT COALESCE(SUM(market_value),0) FROM holdings_daily WHERE account_id=? AND date=?',
                           (row['account_id'], row['date'])).fetchone()[0]
        assert row['nav'] == pytest.approx(row['cash_balance'] + mv)


def cli(x, monkeypatch, *args):
    monkeypatch.setattr('src.forward.runtime.kst_today', lambda: x.clock['now'].date())
    monkeypatch.setattr('src.forward.market_hours.guard_message', lambda: None)
    return daily.main(['--use-stored-prices', *args])


def test_stored_prices_start_15_personal_and_core_then_no_duplicate_initial_fills(build, monkeypatch):
    x = ready(build, 15)
    monkeypatch.setattr('src.forward.prices.refresh_live', lambda *a: pytest.fail('must not refresh'))
    code, stats = run(x)
    assert code == 0 and stats['outcome'] == 'SUCCESS'
    assert stats['successful_accounts'] == 30 and not stats['retryable']
    assert len(stats['account_results']) == 30
    assert x.con.execute('SELECT COUNT(DISTINCT account_id) FROM trades').fetchone()[0] == 30
    first = counts(x.con)
    total_cost = x.con.execute('SELECT SUM(transaction_cost) FROM trades').fetchone()[0]
    assert run(x)[1]['outcome'] == 'SUCCESS'
    assert counts(x.con) == first
    assert x.con.execute('SELECT SUM(transaction_cost) FROM trades').fetchone()[0] == total_cost
    assert_identity(x)
    # The next real evaluation uses the existing positions, not a second initial buy.
    x.prices('2026-10-08')
    code, stats = daily._execute_daily(x.con, x.cfg, '2026-10-08', use_stored_prices=True)
    assert code == 0 and stats['outcome'] == 'SUCCESS'
    assert counts(x.con)['trades'] == first['trades']
    assert counts(x.con)['orders'] == first['orders']
    assert counts(x.con)['nav_daily'] == 60
    assert_identity(x)


def test_without_option_retains_refresh(build, monkeypatch):
    x = ready(build)
    called = []
    monkeypatch.setattr('src.forward.prices.refresh_live', lambda *a: called.append(True) or {
        'asof': DAY, 'new_points': 0, 'stale': []})
    assert daily._execute_daily(x.con, x.cfg, DAY)[0] == 0
    assert called == [True]


def test_existing_pending_is_reused(build):
    x = ready(build)
    aid = account_ids(x)[0]
    oid = create_orders(x.con, aid, {'us_equity': .1}, '2026-10-01', DAY, 'TEST')[0]
    before = dict(x.con.execute('SELECT * FROM orders WHERE order_id=?', (oid,)).fetchone())
    assert run(x)[0] == 0
    after = dict(x.con.execute('SELECT * FROM orders WHERE order_id=?', (oid,)).fetchone())
    assert after == dict(before, status='executed')
    assert x.con.execute('SELECT COUNT(*) FROM orders WHERE account_id=? AND asset_id=?',
                         (aid, 'us_equity')).fetchone()[0] == 1
    assert x.con.execute('SELECT COUNT(*) FROM trades WHERE order_id=?', (oid,)).fetchone()[0] == 1


@pytest.mark.parametrize('stage', ['marker', 'execution', 'valuation', 'database'])
def test_account_failure_rolls_back_and_other_accounts_continue_then_resume(build, monkeypatch, capsys, stage):
    x = ready(build)
    # Fail a personal account with a decision marker; later participants must run.
    aid = x.con.execute("SELECT account_id FROM accounts WHERE account_type='personal'").fetchone()[0]
    from src.forward import db
    marker = db.log_event
    execute = daily.execute_pending
    valuate = daily.valuate
    with monkeypatch.context() as patch:
        if stage == 'marker':
            def fault(con, kind, *args, **kwargs):
                if kind.startswith('DECISION_ORDER:') and args[2] == aid:
                    raise RuntimeError('SECRET_SENTINEL_DO_NOT_LOG')
                return marker(con, kind, *args, **kwargs)
            patch.setattr(db, 'log_event', fault)
        elif stage in ('execution', 'database'):
            def fault(con, account_id, *args, **kwargs):
                result = execute(con, account_id, *args, **kwargs)
                if account_id == aid:
                    if stage == 'database':
                        con.execute('SELECT * FROM deliberately_missing_daily_test_table')
                    raise RuntimeError('SECRET_SENTINEL_DO_NOT_LOG')
                return result
            patch.setattr(daily, 'execute_pending', fault)
        else:
            def fault(con, account_id, *args, **kwargs):
                result = valuate(con, account_id, *args, **kwargs)
                if account_id == aid:
                    raise RuntimeError('SECRET_SENTINEL_DO_NOT_LOG')
                return result
            patch.setattr(daily, 'valuate', fault)
        code, stats = run(x)
    assert code == 1 and stats['outcome'] == 'PARTIAL'
    assert stats['retryable'] and stats['successful_accounts'] == 3
    assert list(stats['account_errors']) == [aid]
    for table in TABLES:
        assert x.con.execute('SELECT COUNT(*) FROM '+table+' WHERE account_id=?', (aid,)).fetchone()[0] == 0
    assert x.con.execute("SELECT COUNT(*) FROM events WHERE account_id=? AND event_type='DAILY_ACCOUNT_FAILED'", (aid,)).fetchone()[0] == 1
    assert 'SECRET_SENTINEL' not in capsys.readouterr().out
    assert 'SECRET_SENTINEL' not in json.dumps(stats)
    before = counts(x.con)
    assert run(x)[1]['outcome'] == 'SUCCESS'
    complete = counts(x.con)
    assert complete['nav_daily'] == before['nav_daily'] + 1 == 4
    assert run(x)[1]['outcome'] == 'SUCCESS'
    assert counts(x.con) == complete
    assert not x.con.execute('SELECT order_id FROM trades GROUP BY order_id HAVING COUNT(*)>1').fetchall()
    assert not x.con.execute("SELECT account_id,event_type FROM events WHERE event_type LIKE ? GROUP BY account_id,event_type HAVING COUNT(*)>1", ('DECISION_ORDER:%',)).fetchall()
    assert_identity(x)


def test_all_account_failures_report_failed_and_remain_retryable(build, monkeypatch):
    x = ready(build)
    monkeypatch.setattr(daily, 'execute_pending', lambda *a: (_ for _ in ()).throw(RuntimeError('fault')))
    code, stats = run(x)
    assert code == 1 and stats['outcome'] == 'FAILED' and stats['retryable']
    assert len(stats['account_errors']) == 4 and not any(counts(x.con).values())


def test_t0_gate_applies_to_stored_prices_even_if_future_prices_exist(build):
    x = ready(build)
    x.clock['now'] = datetime(2026, 10, 6, 17, 17, tzinfo=competition.KST)
    code, stats = run(x)
    assert code == 0 and stats['reason'] == 'AWAITING_T0'
    assert not any(counts(x.con).values())


def test_missing_post_t0_prices_partial_job_can_retry_same_day_then_skip_success(build, monkeypatch):
    x = ready(build, with_prices=False)
    assert cli(x, monkeypatch) == 0
    assert counts(x.con)['orders'] > 0
    assert counts(x.con)['trades'] == counts(x.con)['nav_daily'] == 0
    row = x.con.execute('SELECT status,stats_json FROM scheduled_jobs ORDER BY started_at DESC LIMIT 1').fetchone()
    stats = json.loads(row['stats_json'])
    assert row['status'] == 'skipped' and stats['outcome'] == 'PARTIAL' and stats['retryable']
    # Same KST slot must be allowed after prices arrive; never override the slot.
    x.prices(DAY)
    assert cli(x, monkeypatch) == 0
    assert x.con.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE status='success'").fetchone()[0] == 1
    complete = counts(x.con)
    assert cli(x, monkeypatch) == 0
    assert counts(x.con) == complete
    assert_identity(x)


def test_failed_cli_retains_details_and_retry_preserves_successful_accounts(build, monkeypatch):
    x = ready(build)
    aid = x.con.execute('SELECT account_id FROM accounts').fetchone()[0]
    execute = daily.execute_pending
    with monkeypatch.context() as patch:
        def fault(con, account_id, *args, **kwargs):
            if account_id == aid:
                raise RuntimeError('fault')
            return execute(con, account_id, *args, **kwargs)
        patch.setattr(daily, 'execute_pending', fault)
        assert cli(x, patch) == 1
    row = x.con.execute('SELECT status,stats_json FROM scheduled_jobs ORDER BY started_at DESC LIMIT 1').fetchone()
    assert row['status'] == 'failed'
    assert json.loads(row['stats_json'])['account_errors'][aid]['stage'] == 'execution'
    assert cli(x, monkeypatch) == 0
    complete = counts(x.con)
    assert cli(x, monkeypatch) == 0
    assert counts(x.con) == complete


def test_cli_dry_run_stays_zero_write_and_never_refreshes(build, monkeypatch):
    x = ready(build)
    before = counts(x.con)
    events = x.con.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    monkeypatch.setattr('src.forward.prices.refresh_live', lambda *a: pytest.fail('must not refresh'))
    assert cli(x, monkeypatch, '--dry-run') == 0
    assert counts(x.con) == before
    assert x.con.execute('SELECT COUNT(*) FROM events').fetchone()[0] == events
    assert x.con.execute('SELECT COUNT(*) FROM scheduled_jobs').fetchone()[0] == 0


def test_fx_only_does_not_create_nav_or_fail_normal_wait(build):
    x = ready(build)
    x.con.execute('DELETE FROM prices_daily')
    x.con.execute("INSERT INTO prices_daily VALUES ('__FX__',?,1400,'SYNTHETIC_TEST')", (DAY,))
    x.con.commit()
    code, stats = run(x)
    assert code == 0 and stats['outcome'] == 'PARTIAL' and stats['retryable']
    assert stats['asof'] is None
    assert counts(x.con)['trades'] == counts(x.con)['nav_daily'] == 0


def test_daily_workflow_keeps_collector_and_readonly_default_with_independent_approval():
    workflow = yaml.safe_load(Path('.github/workflows/daily_forward.yml').read_text())
    triggers = workflow.get('on', workflow.get(True))
    assert [r['cron'] for r in triggers['schedule']] == ['30 22 * * *', '17 0 * * *', '17 8 * * *']
    steps = workflow['jobs']['daily']['steps']
    collector = next(s for s in steps if s.get('name') == 'Collect completed prices only')
    assert 'python -m src.forward.run_prices' in collector['run']
    forward = [s for s in steps if s.get('name') == 'Daily forward run']
    assert len(forward) == 1
    step = forward[0]
    assert "github.event.schedule == '17 8 * * *'" in step['if']
    assert 'workflow_dispatch' in step['if']
    assert step['env']['DAILY_ENABLED'] == '${{ vars.FORWARD_DAILY_ENABLED }}'
    assert '--dry-run' in step['run'] and '--use-stored-prices' in step['run']
    assert 'FORWARD_TRADING_ENABLED' not in str(step)
    for name in ('DATABASE_URL', 'CAPSTONE_DESIGN_DATABASE_URL'):
        assert step['env'][name] == '${{ secrets.'+name+' }}'


def test_mixed_existing_traded_account_and_new_accounts(build):
    x = ready(build)
    aid = x.con.execute("SELECT account_id FROM accounts WHERE account_type='personal'").fetchone()[0]
    a = dict(x.con.execute('SELECT * FROM accounts WHERE account_id=?', (aid,)).fetchone())
    with daily._account_transaction(x.con, aid) as tx:
        daily._create_account_orders(tx, a, competition.policy(tx), DAY, DAY, x.cfg['forward_test'])
        daily.execute_pending(tx, aid, DAY, 5, 'CORE_V0.3')
        daily.valuate(tx, aid, DAY, versions_from_cfg(x.cfg), a['initial_capital_krw'])
    before = x.con.execute('SELECT COUNT(*),SUM(transaction_cost) FROM trades WHERE account_id=?', (aid,)).fetchone()
    assert run(x)[1]['outcome'] == 'SUCCESS'
    after = x.con.execute('SELECT COUNT(*),SUM(transaction_cost) FROM trades WHERE account_id=?', (aid,)).fetchone()
    assert tuple(before) == tuple(after)
    assert x.con.execute('SELECT COUNT(DISTINCT account_id) FROM nav_daily').fetchone()[0] == 4


def test_preexisting_pending_survives_failure_and_executes_once_on_retry(build, monkeypatch):
    x = ready(build)
    aid = x.con.execute("SELECT account_id FROM accounts WHERE account_type='personal'").fetchone()[0]
    oid = create_orders(x.con, aid, {'us_equity': .1}, '2026-10-01', DAY, 'TEST')[0]
    before = dict(x.con.execute('SELECT * FROM orders WHERE order_id=?', (oid,)).fetchone())
    execute = daily.execute_pending
    with monkeypatch.context() as patch:
        def fault(con, account_id, *args, **kwargs):
            result = execute(con, account_id, *args, **kwargs)
            if account_id == aid:
                raise RuntimeError('after execution')
            return result
        patch.setattr(daily, 'execute_pending', fault)
        assert run(x)[1]['outcome'] == 'PARTIAL'
    assert dict(x.con.execute('SELECT * FROM orders WHERE order_id=?', (oid,)).fetchone()) == before
    assert x.con.execute('SELECT COUNT(*) FROM trades WHERE order_id=?', (oid,)).fetchone()[0] == 0
    assert run(x)[1]['outcome'] == 'SUCCESS'
    assert x.con.execute('SELECT COUNT(*) FROM trades WHERE order_id=?', (oid,)).fetchone()[0] == 1


def test_two_account_workers_serialize_order_marker_fills_and_nav(build):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    x = ready(build)
    aid = x.con.execute("SELECT account_id FROM accounts WHERE account_type='personal'").fetchone()[0]
    a = dict(x.con.execute('SELECT * FROM accounts WHERE account_id=?', (aid,)).fetchone())
    x.con.commit()
    barrier = Barrier(2)
    def worker():
        con = x.reopen()
        import sqlite3
        con.row_factory = sqlite3.Row
        try:
            barrier.wait(timeout=10)
            with daily._account_transaction(con, aid) as tx:
                daily._create_account_orders(tx, a, competition.policy(tx), DAY, DAY, x.cfg['forward_test'])
                daily.execute_pending(tx, aid, DAY, 5, 'CORE_V0.3')
                daily.valuate(tx, aid, DAY, versions_from_cfg(x.cfg), a['initial_capital_krw'])
        finally:
            con.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        for future in futures:
            future.result(timeout=30)
    assert x.con.execute('SELECT COUNT(*) FROM nav_daily WHERE account_id=?', (aid,)).fetchone()[0] == 1
    assert not x.con.execute('SELECT order_id FROM trades WHERE account_id=? GROUP BY order_id HAVING COUNT(*)>1', (aid,)).fetchall()
    assert not x.con.execute('SELECT asset_id FROM orders WHERE account_id=? GROUP BY asset_id HAVING COUNT(*)>1', (aid,)).fetchall()
    assert x.con.execute('SELECT COUNT(*) FROM events WHERE account_id=? AND event_type LIKE ?', (aid, 'DECISION_ORDER:%')).fetchone()[0] == 1
    assert_identity(x)


@pytest.mark.parametrize(('approved', 'requested', 'readonly'), [
    ('', 'false', True), ('false', 'false', True), ('true', 'false', False), ('true', 'true', True)])
def test_workflow_command_defaults_readonly_and_respects_manual_dry_run(approved, requested, readonly):
    import os
    import subprocess
    workflow = yaml.safe_load(Path('.github/workflows/daily_forward.yml').read_text())
    script = next(s['run'] for s in workflow['jobs']['daily']['steps'] if s.get('name') == 'Daily forward run')
    # Stub the CLI, not a database: exercise the real workflow shell decision.
    result = subprocess.run(['bash', '-c', 'python() { printf "%s\\n" "$@"; };\n' + script],
        env={**os.environ, 'DAILY_ENABLED': approved, 'REQUESTED_DRY_RUN': requested},
        capture_output=True, text=True, check=True)
    args = result.stdout.splitlines()
    assert args[:3] == ['-m', 'src.forward.run_daily', '--use-stored-prices']
    assert ('--dry-run' in args) == readonly
    assert '--force' not in args and '--scheduled-for' not in args
