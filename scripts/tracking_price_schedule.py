"""Local admin tracking prices only. Never starts portfolios or executes trades."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import plistlib
import sqlite3
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.engine import make_url
from src.data.closed_sessions import ClosedSessionProvider
from src.forward.config import load_forward_config, resolve
from src.forward.frozen import load_frozen_benchmark
from src.forward.prices import refresh_live
from src.forward.run_daily import tickers_map


def target(directory):
    directory = Path(directory).resolve(strict=True)
    env = json.loads((directory / 'environment.json').read_text())
    if env.get('DATABASE_BACKEND') != 'sqlite':
        raise ValueError('Local tracking only; remote database targets are refused')
    explicit = env.get('CAPSTONE_DESIGN_DATABASE_URL', '').strip()
    if explicit:
        url = make_url(explicit)
        if url.get_backend_name() != 'sqlite':
            raise ValueError('Local tracking only; remote database targets are refused')
        path = Path(url.database).resolve(strict=True)
    else:
        # Same local path contract as src.db.config.get_design_database_url.
        data_dir = Path(env['CAPSTONE_DATA_DIR']).resolve(strict=True)
        if data_dir != directory:
            raise ValueError('Local data directory does not match the requested target')
        path = (data_dir / 'portfolio_design.db').resolve(strict=True)
    if path.parent != directory or path.name != 'portfolio_design.db':
        raise ValueError('Only the explicitly selected local design DB is permitted')
    return path


def private_json(path, value):
    temp = path.with_suffix('.tmp')
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    temp.replace(path)


def state_directory(path):
    key = sha256(str(path).encode()).hexdigest()[:12]
    directory = ROOT / '.local' / ('tracking-prices-' + key)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def collect(con, now=None, provider=None):
    now = now or datetime.now(timezone.utc)
    floor = con.execute('SELECT MIN(effective_date) FROM portfolio_decisions').fetchone()[0]
    if floor is None:
        return {'status': 'WAITING_FOR_CONFIRMATION', 'new_points': 0, 'stale': []}
    asof = now.astimezone(ZoneInfo('Asia/Seoul')).date().isoformat()
    source = provider or ClosedSessionProvider(now=now)
    cfg = load_forward_config()
    _, meta = load_frozen_benchmark(resolve(cfg['frozen_dir']))
    report = refresh_live(con, tickers_map(con, meta), provider=source, asof=asof,
                          initial_start=str(floor)[:10], observed_only=True)
    report.update(status='PARTIAL_FAILURE' if report['stale'] else 'OK',
                  collected_at=now.isoformat(), first_eligible_date=str(floor)[:10],
                  pending_bars=getattr(source, 'pending', {}),
                  empty_intervals=getattr(source, 'empty', []),
                  latest_dates=dict(con.execute('SELECT asset_id,MAX(date) FROM prices_daily GROUP BY asset_id').fetchall()),
                  scope='LOCAL_DESIGN_PRICES_ONLY', no_orders_or_valuations=True)
    return report


def prices_only_authorizer(action, table, column, database, trigger):
    if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
        return sqlite3.SQLITE_OK if table == 'prices_daily' else sqlite3.SQLITE_DENY
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_ALTER_TABLE,
                  sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_CREATE_TABLE):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def latest_backup(con, destination):
    temporary = destination.with_suffix('.tmp.db')
    with sqlite3.connect(temporary) as copy:
        con.backup(copy)
        if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Tracking backup integrity check failed')
    temporary.chmod(0o600)
    temporary.replace(destination)


def run(directory):
    path = target(directory)
    state = state_directory(path)
    with (state / 'collector.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Price collector already running; skipped')
            return 0
        con = sqlite3.connect(f'file:{path}?mode=rw', uri=True, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            # Explicitly protect immutable replay even if a directory is renamed.
            rows = con.execute("SELECT value FROM forward_state WHERE key='replay_run_id'").fetchall()
            if rows:
                raise ValueError('Replay ledger is not a live observation target')
            backup = state / 'before-first-collection.db'
            if not backup.exists():
                with sqlite3.connect(backup) as copy:
                    con.backup(copy)
                backup.chmod(0o600)
            con.set_authorizer(prices_only_authorizer)
            report = collect(con)
            latest_backup(con, state / 'latest-design.db')
            private_json(state / 'latest.json', report)
            print(json.dumps(report, ensure_ascii=False))
            return int(bool(report['stale']))
        except Exception as error:
            private_json(state / 'latest.json', {'status':'FAILED', 'error_type':type(error).__name__,
                         'collected_at':datetime.now(timezone.utc).isoformat()})
            raise
        finally:
            con.close()


def specification(directory):
    path = target(directory)
    state = state_directory(path)
    return {'Label':'com.robo.tracking-prices.' + sha256(str(path).encode()).hexdigest()[:12],
            'ProgramArguments':[sys.executable, str(Path(__file__).resolve()), 'run', '--directory', str(path.parent)],
            'WorkingDirectory':str(ROOT), 'StartCalendarInterval':{'Minute':17},
            'RunAtLoad':True, 'ProcessType':'Background',
            'EnvironmentVariables':{'TZ':'Asia/Seoul', 'PYTHONUNBUFFERED':'1'},
            'StandardOutPath':str(state/'scheduler.log'), 'StandardErrorPath':str(state/'scheduler-error.log')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'status', 'plan', 'install', 'pause'])
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'run':
        return run(args.directory)
    spec = specification(args.directory)
    state = state_directory(target(args.directory))
    planned = state/'agent.plist'
    planned.write_bytes(plistlib.dumps(spec))
    domain = f'gui/{os.getuid()}'
    if args.action == 'status':
        print((state/'latest.json').read_text() if (state/'latest.json').exists() else 'Not run yet')
        return subprocess.run(['launchctl','print',domain+'/'+spec['Label']]).returncode
    if args.action == 'plan':
        print(planned)
        return 0
    if args.action == 'pause':
        return subprocess.run(['launchctl','bootout',domain+'/'+spec['Label']]).returncode
    dest = Path.home()/'Library'/'LaunchAgents'/(spec['Label']+'.plist')
    if dest.exists() and plistlib.loads(dest.read_bytes()) != spec:
        raise RuntimeError('Different existing scheduler preserved; reconcile it explicitly')
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(planned.read_bytes())
        dest.chmod(0o600)
    active = subprocess.run(['launchctl','print',domain+'/'+spec['Label']], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if active.returncode:
        subprocess.run(['launchctl','bootstrap',domain,str(dest)], check=True)
    print(f"{spec['Label']}: hourly at :17, only while this Mac is awake; no trades/NAV")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
