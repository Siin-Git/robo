"""Persistent local, real-clock market paper operation. No remote DB or seeding."""
from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
LABEL = 'com.roboadvisor.local-forward.daily'
KST = ZoneInfo('Asia/Seoul')


def environment(directory, api_port=8073):
    """Explicit process values win over dotenv, including all import/PG settings."""
    return dict(os.environ, APP_PROFILE='local', CAPSTONE_DEMO='1',
        CAPSTONE_MARKET_COMPARISON='1', CAPSTONE_DATA_DIR=str(Path(directory).resolve()),
        DATABASE_BACKEND='sqlite', DATABASE_URL='', CAPSTONE_DESIGN_DATABASE_URL='',
        DESIGN_PRICE_SOURCE='', CAPSTONE_LAB_ACCOUNTS_JSON='', CAPSTONE_INVITATIONS_JSON='',
        AUTH_COOKIE_SECURE='false', ALLOW_PUBLIC_REGISTRATION='false',
        FORWARD_EXECUTOR='notebook', TZ='Asia/Seoul',
        NEXT_PUBLIC_APP_PROFILE='local', NEXT_PUBLIC_CAPSTONE_DEMO='1',
        NEXT_PUBLIC_LAB_MEETING='1', NEXT_DIST_DIR='.next-local-operation',
        FASTAPI_INTERNAL_URL=f'http://127.0.0.1:{api_port}')


def read_settings(directory):
    directory = Path(directory).resolve()
    settings = json.loads((directory/'operation.json').read_text())
    if settings.get('mode') != 'REAL_MARKET_PAPER' or settings.get('clock') != 'SYSTEM_KST':
        raise ValueError('Require the real-market local operation manifest; demo fixtures are not accepted.')
    if settings['data_dir'] != str(directory):
        raise ValueError('Operation manifest belongs to a different directory.')
    return settings


def initialize(directory, web_port=3073, api_port=8073):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory/'operation.json'
    if marker.exists():
        return read_settings(directory)
    if any(directory.glob('*.db')) or (directory/'accounts.json').exists():
        raise ValueError('Existing unmarked data is preserved; choose a new operation directory.')
    os.chmod(directory, 0o700)
    env = environment(directory, api_port)
    # Migrate fresh stores explicitly; no original account/decision/price copy.
    for filename in ('capstone_demo.db', 'portfolio_design.db'):
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT,
            env={**env, 'DATABASE_URL':f'sqlite:///{directory/filename}'}, check=True)
    subprocess.run([sys.executable, '-m', 'src.local.lab_meeting', '--name', 'local-operation',
        '--out', str(directory/'accounts.json')], cwd=ROOT, env=env, check=True)
    # Only theme/ticker configuration is shared. The daily engine needs it even
    # before the first API user opens their design workspace.
    with sqlite3.connect(directory/'capstone_demo.db') as auth, sqlite3.connect(directory/'portfolio_design.db') as design:
        columns = [r[1] for r in auth.execute('PRAGMA table_info(themes)')]
        placeholders = ','.join('?' for _ in columns)
        design.executemany(f'INSERT INTO themes ({",".join(columns)}) VALUES ({placeholders})',
            auth.execute('SELECT '+','.join(columns)+' FROM themes').fetchall())
        assert design.execute('SELECT COUNT(*) FROM portfolio_decisions').fetchone()[0] == 0
        assert design.execute('SELECT COUNT(*) FROM prices_daily').fetchone()[0] == 0
    settings = dict(mode='REAL_MARKET_PAPER', clock='SYSTEM_KST', data_dir=str(directory),
        web_port=web_port, api_port=api_port, source_dir=str(ROOT), label=LABEL,
        daily_kst={'hour':7,'minute':30}, created_at=datetime.now(KST).isoformat())
    marker.write_text(json.dumps(settings, indent=2))
    (directory/'logs').mkdir(exist_ok=True)
    return settings


@contextmanager
def exclusive(directory, name):
    """Single local process across manual/launchd starts, in addition to DB slots."""
    with (Path(directory)/f'{name}.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'{name} is already running; existing process is preserved.')
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def next_schedule(now=None):
    now = now or datetime.now(KST)
    today = now.replace(hour=7, minute=30, second=0, microsecond=0)
    return (today if now < today else today + timedelta(days=1)).isoformat()


def ledger_summary(directory):
    path = Path(directory)/'portfolio_design.db'
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as con:
        con.row_factory = sqlite3.Row
        counts = {t:con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
            for t in ('portfolio_decisions','orders','trades','nav_daily','prices_daily')}
        jobs = [dict(r) for r in con.execute('SELECT * FROM scheduled_jobs ORDER BY started_at DESC LIMIT 3')]
        latest = con.execute("SELECT MAX(date) FROM prices_daily WHERE asset_id != '__FX__'").fetchone()[0]
        future = con.execute('SELECT COUNT(*) FROM portfolio_decisions WHERE effective_date > ?',
            (datetime.now(KST).date().isoformat(),)).fetchone()[0]
        synthetic = con.execute("SELECT COUNT(*) FROM prices_daily WHERE source LIKE 'SYNTHETIC%'").fetchone()[0]
    reasons = []
    if not counts['portfolio_decisions']:reasons.append('AWAITING_USER_CONFIRMATION')
    if future:reasons.append('TARGET_EFFECTIVE_DATE_PENDING')
    if not counts['trades']:reasons.append('AWAITING_ELIGIBLE_MARKET_CLOSE_OR_CONFIRMATION')
    return dict(operating_db=str(path.resolve()), latest_price_date=latest, counts=counts,
        synthetic_price_rows=synthetic, waiting_reasons=reasons, recent_jobs=jobs)


def run_daily(directory):
    settings = read_settings(directory)
    directory = Path(directory)
    with exclusive(directory, 'daily'):
        started = datetime.now(KST).isoformat()
        logfile = directory/'logs'/'daily.log'
        with logfile.open('a') as log:
            log.write('\nLOCAL REAL MARKET RUN '+started+'\n');log.flush()
            result = subprocess.run([sys.executable, '-m', 'src.forward.run_daily'], cwd=ROOT,
                env=environment(directory, settings['api_port']), stdout=log, stderr=log)
        summary = ledger_summary(directory)
        status = 'MARKET_HOURS_PROTECTED' if result.returncode == 2 else 'FAILED' if result.returncode else 'COMPLETED'
        if result.returncode == 0 and summary['recent_jobs']:
            latest = summary['recent_jobs'][0]['status']
            if latest in ('skipped','locked'):
                status = latest.upper()
        record = dict(started_at=started, completed_at=datetime.now(KST).isoformat(),
            exit_code=result.returncode, status=status, next_calendar_run=next_schedule(), **summary)
        (directory/'last-run.json').write_text(json.dumps(record, indent=2))
        print(json.dumps(record, indent=2))
        return result.returncode
