"""Exercise the shipped manual runner without operating credentials or DB access."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


WORKFLOW = Path('.github/workflows/bootstrap_unready_portfolios.yml')


def workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def test_manual_only_release_branch_and_shared_writer_lock():
    doc = workflow()
    triggers = doc.get('on', doc.get(True))
    assert set(triggers) == {'workflow_dispatch'}
    inputs = triggers['workflow_dispatch']['inputs']
    assert inputs['apply']['type'] == 'boolean'
    assert inputs['apply']['default'] is False
    assert inputs['confirmation']['default'] == ''
    assert doc['permissions'] == {'contents': 'read'}
    for name in ('daily_forward.yml', 'weekly_views.yml', 'monthly_rebalance.yml'):
        existing = yaml.safe_load((WORKFLOW.parent / name).read_text())
        assert doc['concurrency'] == existing['concurrency']
    assert doc['concurrency']['cancel-in-progress'] is False
    job = doc['jobs']['bootstrap']
    assert job['if'] == "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/release/public-operation' }}"
    run_step = job['steps'][-1]
    assert run_step['env']['DATABASE_URL'] == '${{ secrets.DATABASE_URL }}'
    assert run_step['env']['CAPSTONE_DESIGN_DATABASE_URL'] == '${{ secrets.CAPSTONE_DESIGN_DATABASE_URL }}'
    assert not any(k in run_step['env'] for k in ('FORWARD_DAILY_ENABLED', 'FORWARD_TRADING_ENABLED'))
    assert not any('run_daily' in s.get('run', '') or 'alembic' in s.get('run', '') for s in job['steps'])


def run_command(tmp_path, **overrides):
    # Real workflow heredoc, imported services replaced only in this disposable process.
    # Record every read/call to verify rejected apply cannot even query a cohort.
    fake = tmp_path / 'stubs'
    for relative in ('src', 'src/forward', 'scripts'):
        directory = fake / relative
        directory.mkdir(parents=True, exist_ok=True)
        (directory / '__init__.py').write_text('')
    (fake / 'src/forward/competition.py').write_text('''
import json, os
def read_cohort():
    with open(os.environ['CALLS'], 'a') as f: f.write('read_cohort\\n')
    if os.environ.get('COHORT_ERROR'):
        raise RuntimeError(os.environ['DATABASE_URL'])
    return None if os.environ.get('NO_COHORT') else {'cohort_id': 'active-test-cohort'}
''')
    (fake / 'scripts/bootstrap_unready_portfolios.py').write_text('''
import json, os
def main(args):
    with open(os.environ['CALLS'], 'a') as f: f.write(json.dumps(args) + '\\n')
    if os.environ.get('MAIN_ERROR'):
        raise RuntimeError(os.environ['CAPSTONE_DESIGN_DATABASE_URL'])
    return int(os.environ.get('MAIN_RESULT', '0'))
''')
    calls = tmp_path / 'calls.txt'
    env = {**os.environ, 'PYTHONPATH': str(fake), 'PATH': str(Path(sys.executable).parent) + ':' + os.environ['PATH'],
           'APP_PROFILE': 'local', 'CAPSTONE_DEMO': '1', 'DATABASE_BACKEND': 'postgres',
           'DATABASE_URL': 'postgresql://secret-auth-sentinel',
           'CAPSTONE_DESIGN_DATABASE_URL': 'postgresql://secret-design-sentinel',
           'REQUESTED_APPLY': 'false', 'APPLY_CONFIRMATION': '', 'CALLS': str(calls), **overrides}
    command = workflow()['jobs']['bootstrap']['steps'][-1]['run']
    result = subprocess.run(['bash', '-e', '-c', command], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert 'secret-auth-sentinel' not in result.stdout + result.stderr
    assert 'secret-design-sentinel' not in result.stdout + result.stderr
    return result, calls.read_text().splitlines() if calls.exists() else []


@pytest.mark.parametrize(('apply', 'confirmation', 'mode'), [
    ('false', '', '--dry-run'), ('false', 'APPLY_UNREADY_PORTFOLIOS', '--dry-run'),
    ('true', 'APPLY_UNREADY_PORTFOLIOS', '--apply'),
])
def test_actual_command_passes_only_explicit_mode_and_read_cohort(tmp_path, apply, confirmation, mode):
    result, calls = run_command(tmp_path, REQUESTED_APPLY=apply, APPLY_CONFIRMATION=confirmation)
    assert result.returncode == 0
    assert calls[0] == 'read_cohort'
    assert json.loads(calls[1]) == [mode, '--expected-cohort', 'active-test-cohort', '--max-new', '10']


@pytest.mark.parametrize(('overrides', 'code'), [
    ({'REQUESTED_APPLY': 'true'}, 'APPLY_CONFIRMATION_REQUIRED'),
    ({'REQUESTED_APPLY': 'true', 'APPLY_CONFIRMATION': '$(touch injected)'}, 'APPLY_CONFIRMATION_REQUIRED'),
    ({'REQUESTED_APPLY': 'yes'}, 'INVALID_APPLY_INPUT'),
    ({'DATABASE_URL': ''}, 'DB_ENVIRONMENT_MISSING'),
    ({'CAPSTONE_DESIGN_DATABASE_URL': ''}, 'DB_ENVIRONMENT_MISSING'),
    ({'APP_PROFILE': 'capstone'}, 'ENVIRONMENT_MISMATCH'),
])
def test_rejected_configuration_never_reads_or_writes(tmp_path, overrides, code):
    result, calls = run_command(tmp_path, **overrides)
    assert result.returncode != 0 and code in result.stderr
    assert calls == []
    assert not (tmp_path / 'injected').exists()


@pytest.mark.parametrize('failure', ['COHORT_ERROR', 'MAIN_ERROR', 'NO_COHORT', 'MAIN_RESULT'])
def test_failures_are_not_success_or_credential_output(tmp_path, failure):
    result, calls = run_command(tmp_path, **{failure: '1'})
    assert result.returncode != 0
    if failure in ('COHORT_ERROR', 'MAIN_ERROR'):
        assert result.stdout.strip() == 'FAILED: RuntimeError'
    if failure == 'NO_COHORT':
        assert result.stderr.strip() == 'ACTIVE_COHORT_REQUIRED'
        assert calls == ['read_cohort']
