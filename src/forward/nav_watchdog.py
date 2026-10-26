"""Bounded server-side NAV audit/recovery using the existing daily engine.

No dates, job databases, locks or initial positions can be overridden by the CLI.
Three KST windows (18/20/22) permit at most one recovery attempt each per day.
"""
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from . import jobs
from .competition import policy
from .job_outcome import incomplete_daily, daily_outcome
from .nav_evidence import normal_forward_nav, payload

KST = ZoneInfo('Asia/Seoul')
WINDOWS = (18, 20, 22)
RETRY_STATES = {'NAV_MISSING', 'PRICE_WAIT'}


def stalled(rows):
    # Workflows time out after 25 minutes. Retain the lock, but do not hide an
    # abandoned attempt behind a forever-green RUNNING result.
    for row in rows:
        try:
            started = datetime.fromisoformat(str(row['started_at']))
            if started.tzinfo is None:
                started = started.replace(tzinfo=ZoneInfo('UTC'))
            if (datetime.now(KST) - started).total_seconds() > 30 * 60:
                return True
        except (TypeError, ValueError):
            return True
    return False


def audit(con, cfg, day):
    gate = policy(con)
    result = {'date': day, 'state': 'POLICY_BLOCKED', 'retry_allowed': False,
              'reason': gate.get('reason'), 'expected_accounts': 0, 'normal_accounts': 0,
              'personalized': 0, 'core': 0, 'complete_pairs': 0}
    if not gate.get('managed') or gate.get('blocked'):
        return result
    members = gate['schedule']['members']
    expected = {aid for member in members for aid in member['account_ids']}
    result['expected_accounts'] = len(expected)
    if not expected or len(expected) != 2 * len(members):
        return dict(result, reason='INVALID_ACCOUNT_ROSTER')
    accounts = {r['account_id']: dict(r) for r in con.execute('SELECT * FROM accounts').fetchall()}
    for member in members:
        pair = [accounts.get(aid) for aid in member['account_ids']]
        if (any(not a or a['status'] != 'active' or a['participant_id'] != member['participant_id'] for a in pair)
                or {a['account_type'] for a in pair} != {'personal', 'core'}):
            return dict(result, reason='INVALID_ACCOUNT_ROSTER')
    if (con.execute("SELECT 1 FROM forward_state WHERE key='replay_run_id'").fetchone()
            or con.execute("SELECT 1 FROM prices_daily WHERE LOWER(source) LIKE ? LIMIT 1", ("synthetic%",)).fetchone()):
        return dict(result, state='UNVERIFIED_DATA', reason='NON_FORWARD_STORE')
    for row in con.execute("SELECT account_id,payload_json FROM events WHERE event_type='NAV_CALCULATED'").fetchall():
        if row['account_id'] in expected and payload(row['payload_json']).get('data_kind') in {'TEST_FIXTURE', 'HISTORICAL_REPLAY'}:
            return dict(result, state='UNVERIFIED_DATA', reason='NON_FORWARD_HISTORY')
    version = cfg['forward_test']['benchmark_version']
    normal, existing = set(), set()
    for aid in expected:
        if con.execute('SELECT 1 FROM nav_daily WHERE account_id=? AND date=?', (aid, day)).fetchone():
            existing.add(aid)
        if normal_forward_nav(con, aid, day, version):
            normal.add(aid)
    result.update(normal_accounts=len(normal),
                  personalized=sum(accounts[a]['account_type'] == 'personal' for a in normal),
                  core=sum(accounts[a]['account_type'] == 'core' for a in normal),
                  complete_pairs=sum(set(m['account_ids']).issubset(normal) for m in members))
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM scheduled_jobs WHERE job_type='daily' AND scheduled_for=? ORDER BY started_at DESC",
        (day,)).fetchall()]
    recorded = next((r for r in rows if r['status'] != 'skipped' or payload(r['stats_json'])), None)
    result['job_state'] = daily_outcome(recorded['status'], payload(recorded['stats_json']))['state'] if recorded else 'NO_JOB'
    # Never break a running lock, even if its age would allow generic CLI recovery.
    running = [r for r in rows if r['status'] == 'running']
    if running:
        return dict(result, state='RUNNING_REVIEW_REQUIRED' if stalled(running) else 'RUNNING', reason='DAILY_LOCK_RETAINED')
    if existing - normal:
        return dict(result, state='NAV_REVIEW_REQUIRED', reason='EXISTING_NAV_NOT_VERIFIED')
    due = {r['account_id'] for r in con.execute(
        "SELECT account_id FROM orders WHERE status='pending' AND effective_at<=?", (day,)).fetchall()} & expected
    if normal & due:
        return dict(result, state='NAV_REVIEW_REQUIRED', reason='ORDERS_AFTER_SAVED_NAV')
    if normal == expected:
        if result['job_state'] in {'EVALUATION_FAILED', 'PARTIAL'}:
            return dict(result, state='NAV_REVIEW_REQUIRED', reason='NAV_PRESENT_JOB_FAILED')
        return dict(result, state='NAV_COMPLETE', reason=None)
    if any(r['status'] == 'success' and not incomplete_daily(payload(r['stats_json'])) for r in rows):
        return dict(result, state='JOB_NAV_MISMATCH', reason='SUCCESS_SLOT_RETAINED')
    # Require today's actual investable observations; FX alone never creates a NAV date.
    price = con.execute("SELECT MAX(date) d FROM prices_daily WHERE asset_id!='__FX__' AND date<=?",
                        (day,)).fetchone()['d']
    result['latest_price_date'] = str(price)[:10] if price else None
    return dict(result, state='NAV_MISSING' if result['latest_price_date'] == day else 'PRICE_WAIT',
                reason=None, retry_allowed=True)


def recover(con, cfg, db_path, *, now, repair=False, collect=None, evaluate=None):
    if now.tzinfo is None:
        raise ValueError('Aware clock required')
    now = now.astimezone(KST)
    day = now.date().isoformat()
    report = {'checked_at': now.isoformat(), 'repair_requested': repair, 'attempted': False}
    before = audit(con, cfg, day)
    report.update(before=before, after=before, state=before['state'])
    if not repair or before['state'] not in RETRY_STATES:
        return report
    if now.weekday() >= 5 or now.hour < WINDOWS[0]:
        return dict(report, state='OUTSIDE_RECOVERY_WINDOW')
    # Block abandoned watchdogs too; automatic lock stealing is not recovery.
    running = con.execute("SELECT started_at FROM scheduled_jobs WHERE job_type LIKE ? AND scheduled_for=? AND status='running'",
                          ("navcheck-%", day)).fetchall()
    if running:
        return dict(report, state='RECOVERY_REVIEW_REQUIRED' if stalled(running) else 'RECOVERY_RUNNING')
    slot = max(hour for hour in WINDOWS if hour <= now.hour)
    con.commit()  # End the read transaction before the registry claims its own lock.
    jid, decision = jobs.claim_job(None, f'navcheck-{slot}', day,
                                   os.environ.get('GITHUB_RUN_ID'), sqlite_path=db_path)
    if decision != 'run':
        return dict(report, state='WINDOW_ALREADY_ATTEMPTED', window=slot)
    report.update(attempted=True, window=slot)
    try:
        report['collector_exit'] = collect()
        con.rollback()  # Observe the collector's committed prices.
        current = audit(con, cfg, day)
        # No valuation on collector errors, stale-day prices or a newly blocked gate.
        if report['collector_exit'] == 0 and current['state'] == 'NAV_MISSING':
            report['daily_exit'] = evaluate()
            con.rollback()
        report['after'] = audit(con, cfg, day)
        report['state'] = report['after']['state']
        if report['collector_exit'] != 0:
            report['state'] = 'PRICE_COLLECTION_FAILED'
    except Exception as error:
        con.rollback()
        report.update(state='RECOVERY_ERROR', error_type=type(error).__name__)
    finally:
        con.rollback()
        # Consume this window even on failed/incomplete recovery. No busy-loop retry.
        # This is a watchdog attempt, never a daily valuation success record.
        jobs.complete_job(None, jid, report, sqlite_path=db_path)
    return report


def main(argv=None):
    import argparse
    from .config import load_forward_config
    from .db import connect
    from .runtime import get_database_path
    from .run_prices import operating_store
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repair', action='store_true', help='Opt in to bounded same-day recovery')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    con = None
    try:
        if not (os.environ.get('APP_PROFILE') == 'local' and os.environ.get('CAPSTONE_DEMO') == '1'
                and os.environ.get('FORWARD_EXECUTOR') == 'actions'
                and os.environ.get('FORWARD_DAILY_ENABLED') == 'true'):
            raise ValueError('Operating mode must be explicitly enabled')
        # Verify explicit production design target read-only before any registry/financial write.
        with operating_store(read_only=True) as store:
            target = store.target()
            if target['database'] != 'robo_design' or target['schema_revisions'] != ['0008']:
                raise ValueError('Unexpected operating database or schema')
        cfg = load_forward_config()
        path = get_database_path()
        con = connect(path)
        if not args.repair:
            con.execute('SET TRANSACTION READ ONLY')
        started = datetime.now(KST)
        def collect():
            from .run_prices import main as prices
            return prices(['--start', '2026-10-05', '--expected-database', 'robo_design',
                           '--expected-revision', '0008', '--output', str(args.output.with_name('recovery-prices.json'))])
        def evaluate():
            if datetime.now(KST).date() != started.date():
                return 2  # Never roll an old recovery window into a new date.
            from .run_daily import main as daily
            return daily(['--use-stored-prices', '--missing-nav-only', '--scheduled-for', started.date().isoformat()])
        report = recover(con, cfg, path, now=started, repair=args.repair,
                         collect=collect, evaluate=evaluate)
    except Exception as error:
        report = {'state': 'CHECK_FAILED', 'error_type': type(error).__name__, 'repair_requested': args.repair}
    finally:
        if con:
            con.rollback()
            con.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        after = report.get('after', {})
        with open(summary, 'a') as stream:
            stream.write(f"## NAV 점검: {report['state']}\n\n기준일: {after.get('date', '미확보')}\n\n"
                         f"정상 평가: {after.get('normal_accounts', 0)}/{after.get('expected_accounts', 0)}계좌 · "
                         f"Personalized {after.get('personalized', 0)} / CORE {after.get('core', 0)} · "
                         f"완료 쌍 {after.get('complete_pairs', 0)}\n\n재시도 실행: {report.get('attempted', False)}\n")
    # Missing NAV is not a successful workflow; a report artifact survives either exit.
    return 0 if report['state'] in {'NAV_COMPLETE', 'OUTSIDE_RECOVERY_WINDOW', 'RUNNING', 'RECOVERY_RUNNING'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
