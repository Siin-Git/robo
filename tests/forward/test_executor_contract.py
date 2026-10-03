from datetime import datetime,timezone
from pathlib import Path
import yaml
from src.forward.runtime import configured_executor
import pytest

def test_unattended_executor_is_explicit(monkeypatch):
    monkeypatch.delenv('FORWARD_EXECUTOR',raising=False)
    assert configured_executor()=='disabled'
    monkeypatch.setenv('FORWARD_EXECUTOR','actions');assert configured_executor()=='actions'
    monkeypatch.setenv('FORWARD_EXECUTOR','unknown')
    with pytest.raises(ValueError):configured_executor()

def test_actions_use_capstone_design_db_and_owner_gate():
    for file in ('daily_forward.yml','monthly_rebalance.yml','weekly_views.yml'):
        workflow=yaml.safe_load((Path('.github/workflows')/file).read_text())
        job=next(iter(workflow['jobs'].values()))
        assert "vars.FORWARD_EXECUTOR == 'actions'" in job['if']
        env=job['steps'][-1]['env']
        assert env['APP_PROFILE']=='local' and env['CAPSTONE_DEMO']=='1'
        assert env['CAPSTONE_DESIGN_DATABASE_URL']=='${{ secrets.CAPSTONE_DESIGN_DATABASE_URL }}'
        assert env['DATABASE_BACKEND']=='postgres' and env['TZ']=='Asia/Seoul'
