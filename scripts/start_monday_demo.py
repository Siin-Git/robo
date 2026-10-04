"""Disposable SYNTHETIC Monday demo. Never connects to an operating database.

The test clock exists only in this launcher process; the application has no new
clock/configuration feature. Use a NEW /private/tmp directory on each run.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

from start_local import is_port_in_use, npm_cmd, wait

ROOT = Path(__file__).resolve().parents[1]
MONDAY = '2026-10-05T03:00:00+00:00'


def local_environment(directory, api_port):
    # Override developer dotenv settings before importing any application code.
    os.environ.update(APP_PROFILE='local', CAPSTONE_DEMO='1',
        CAPSTONE_MARKET_COMPARISON='1', DATABASE_BACKEND='sqlite',
        DATABASE_URL='', CAPSTONE_DESIGN_DATABASE_URL='',
        CAPSTONE_DATA_DIR=str(directory), AUTH_COOKIE_SECURE='false',
        ALLOW_PUBLIC_REGISTRATION='false', NEXT_PUBLIC_APP_PROFILE='local',
        NEXT_PUBLIC_CAPSTONE_DEMO='1', NEXT_PUBLIC_LAB_MEETING='1',
        NEXT_DIST_DIR='.next-monday-demo',
        FASTAPI_INTERNAL_URL=f'http://127.0.0.1:{api_port}')
    return dict(os.environ)


def prepare(directory, env):
    subprocess.run([sys.executable, '-m', 'src.local.lab_meeting', '--out',
        str(directory/'accounts.json')], cwd=ROOT, env=env, check=True)
    for index in (0, 1):
        subprocess.run([sys.executable, str(ROOT/'scripts/seed_pending_decision_fixture.py'),
            '--directory', str(directory), '--account-index', str(index)],
            cwd=ROOT, env=env, check=True)
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.api.services import _common as common
    accounts = json.loads((directory/'accounts.json').read_text())['accounts']
    cases = []
    with TestClient(app) as client:
        for index, days in ((0, [MONDAY]), (1, ['2026-10-03T03:00:00+00:00', MONDAY])):
            client.cookies.clear()
            common.now_utc = lambda: datetime.fromisoformat(MONDAY)
            account = accounts[index]
            response = client.post('/api/v1/auth/login', json={
                'email': account['email'], 'password': account['password']})
            assert response.status_code == 200
            headers = {'X-CSRF-Token': client.cookies['ra_csrf']}
            original = client.get('/api/v1/me/decisions').json()['items'][0]
            frontier = client.get('/api/v1/me/frontier').json()
            for stamp in days:
                common.now_utc = lambda stamp=stamp: datetime.fromisoformat(stamp)
                current = client.get('/api/v1/me/decisions').json()['items'][0]
                choice = client.post('/api/v1/me/portfolio/choices', headers=headers,
                    json={'decision_id': current['decision_id'], 'target_id': current['target_id'],
                        'action': 'ADJUST', 'reason': 'SYNTHETIC Monday demo only',
                        'request_key': f'monday-fixture-{index}-{current["version"]}'})
                assert choice.status_code == 200, choice.text
                response = client.post('/api/v1/me/onboarding/complete', headers=headers,
                    json={'frontier_id': frontier['benchmark_frontier_id'], 'theme_ids': ['biotech'],
                        'reason': 'SYNTHETIC Monday demo, not actual operation',
                        'expected_decision_id': current['decision_id'],
                        'adjustment_choice_id': choice.json()['choice_id']})
                assert response.status_code == 200, response.text
            common.now_utc = lambda: datetime.fromisoformat(MONDAY)
            report = client.get('/api/v1/me/performance/dashboard').json()
            assert report['decision_context']['as_of'] == '2026-10-05'
            assert report['observations'] == (2 if index == 0 else 0)
            assert report['decision_context']['pending_decision']['target_effective_date'] == '2026-10-06'
            old = client.get(f'/api/v1/me/decisions/{original["decision_id"]}/review').json()
            assert old['actual']['observations'] == 2
            cases.append({'account_index': index, 'original_decision_id': original['decision_id'],
                'expected_active_version': 1 if index == 0 else 2,
                'expected_pending_version': 2 if index == 0 else 3,
                'expected_observations': 2 if index == 0 else 0})
    (directory/'monday-fixture.json').write_text(json.dumps({
        'data_kind': 'TEST_FIXTURE', 'clock': MONDAY, 'cases': cases}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--port', type=int, default=3063)
    parser.add_argument('--api-port', type=int, default=8063)
    parser.add_argument('--serve-api', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_relative_to(Path('/private/tmp')):
        parser.error('Only a disposable /private/tmp directory is allowed.')
    env = local_environment(directory, args.api_port)
    if args.serve_api:
        if not (directory/'monday-fixture.json').is_file():
            parser.error('Require this launcher\'s synthetic Monday fixture.')
        sys.path.insert(0, str(ROOT))
        from src.api.services import _common as common
        common.now_utc = lambda: datetime.fromisoformat(MONDAY)
        import uvicorn
        uvicorn.run('src.api.main:app', host='127.0.0.1', port=args.api_port)
        return
    if directory.exists() and any(directory.iterdir()):
        parser.error('Require a NEW empty directory; existing data is never changed.')
    if args.port == args.api_port or any(is_port_in_use(p) for p in (args.port, args.api_port)):
        parser.error('Choose two unused ports; existing servers are preserved.')
    npm = npm_cmd()
    if npm is None:
        parser.error('npm is required.')
    directory.mkdir(parents=True, exist_ok=True)
    prepare(directory, env)
    processes = []
    try:
        processes.append(subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
            '--directory', str(directory), '--serve-api', '--api-port', str(args.api_port)],
            cwd=ROOT, env=env))
        processes.append(subprocess.Popen([npm, 'run', 'dev', '--', '--hostname',
            '127.0.0.1', '--port', str(args.port)], cwd=ROOT/'web', env=env))
        if not wait(f'http://127.0.0.1:{args.api_port}/health', 30) or not wait(f'http://127.0.0.1:{args.port}/login', 45):
            raise RuntimeError('Local demo failed to start; inspect logs.')
        print(f'SYNTHETIC MONDAY 2026-10-05 KST: http://127.0.0.1:{args.port}/login', flush=True)
        print('Accounts 1/2: current + pending / new-current record shortage + previous history.', flush=True)
        if (directory/'ledger-comparison-fixture.json').is_file():
            print('TEST_FIXTURE: 1=current+pending/3 valuations, 2=0/new-current with old history, 3=1 valuation, 4=late start/2 valuations, 5=fresh, 6=append test.', flush=True)
        elif (directory/'ledger-observation-gap-fixture.json').is_file():
            print('TEST_FIXTURE: 1=A/current+pending/100-50-100, 4=B/100-null-101, 2=0/new-current with old history, 3=1 valuation, 5+=fresh. Synthetic NAV inputs only.', flush=True)
        else:
            print('Accounts 3+: fresh participants. Private credentials are only in accounts.json.', flush=True)
        print('Ctrl+C stops both servers. This is not production or actual Monday returns.', flush=True)
        processes[0].wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == '__main__':
    main()
