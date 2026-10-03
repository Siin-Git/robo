"""Create a past confirmed decision in a NEW disposable lab fixture only.

Confirmation is backdated in this subprocess solely to reproduce a future revision
while the real API clock remains unchanged. No historical original estimate is
backfilled in an existing account. All fixture data is explicitly synthetic.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_relative_to(Path('/private/tmp')):
        parser.error('Only a disposable /private/tmp lab fixture is allowed.')
    if not (directory/'accounts.json').is_file():
        parser.error('Create fresh local lab accounts first.')
    # Explicit process environment wins over ignored developer dotenv files.
    os.environ.update(APP_PROFILE='local', CAPSTONE_DEMO='1', CAPSTONE_MARKET_COMPARISON='1',
        DATABASE_BACKEND='sqlite', DATABASE_URL='', CAPSTONE_DESIGN_DATABASE_URL='',
        CAPSTONE_DATA_DIR=str(directory), AUTH_COOKIE_SECURE='false', ALLOW_PUBLIC_REGISTRATION='false')
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.api.services import _common as common
    account = json.loads((directory/'accounts.json').read_text())['accounts'][0]
    with TestClient(app) as client:
        assert client.post('/api/v1/auth/login',json={'email':account['email'],'password':account['password']}).status_code == 200
        existing = client.get('/api/v1/me/decisions').json()['items']
        if existing:
            parser.error('Require a fresh fixture user; never alter existing decisions.')
        frontier = client.get('/api/v1/me/frontier').json()
        common.now_utc = lambda: datetime.fromisoformat('2026-09-30T03:00:00+00:00')
        response = client.post('/api/v1/me/onboarding/complete',headers={'X-CSRF-Token':client.cookies['ra_csrf']},
            json={'frontier_id':frontier['benchmark_frontier_id'],'theme_ids':['ai'],
                  'reason':'SYNTHETIC regression fixture: past decision, not real history'})
        assert response.status_code == 200, response.text
        original = client.get('/api/v1/me/decisions').json()['items'][0]
    subprocess.run([sys.executable,str(ROOT/'scripts/seed_integration_fixture.py'),
        '--database',str(directory/'portfolio_design.db'),'--account',original['account_id']],
        cwd=ROOT,check=True,env={**os.environ,'APP_PROFILE':'validation','CAPSTONE_DEMO':'0'})
    (directory/'pending-fixture.json').write_text(json.dumps({'original':original},indent=2))
    print('TEST_FIXTURE only; immutable synthetic original decision and past valuations created.')


if __name__ == '__main__':
    main()
