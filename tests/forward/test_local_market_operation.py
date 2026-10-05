"""Disposable-only end-to-end market pipeline; no ongoing operation DB touched."""
from datetime import datetime
import json
import sqlite3
import pandas as pd
import pytest

from src.local.operation import environment, initialize, exclusive, read_settings, next_schedule, ledger_summary


def test_environment_cannot_inherit_remote_or_demo_inputs(tmp_path, monkeypatch):
    for key in ('DATABASE_URL','CAPSTONE_DESIGN_DATABASE_URL','DESIGN_PRICE_SOURCE','CAPSTONE_LAB_ACCOUNTS_JSON'):
        monkeypatch.setenv(key,'remote-or-demo-value')
    env=environment(tmp_path)
    assert env['DATABASE_BACKEND']=='sqlite'
    assert all(env[k]=='' for k in ('DATABASE_URL','CAPSTONE_DESIGN_DATABASE_URL','DESIGN_PRICE_SOURCE','CAPSTONE_LAB_ACCOUNTS_JSON'))
    assert env['FORWARD_EXECUTOR']=='notebook' and env['TZ']=='Asia/Seoul'
    with exclusive(tmp_path,'daily'):
        with pytest.raises(RuntimeError):
            with exclusive(tmp_path,'daily'):pass


def test_unknown_or_synthetic_store_is_not_adopted(tmp_path):
    (tmp_path/'portfolio_design.db').touch()
    with pytest.raises(ValueError):initialize(tmp_path)
    (tmp_path/'operation.json').write_text(json.dumps({'mode':'TEST_FIXTURE','clock':'FIXED'}))
    with pytest.raises(ValueError):read_settings(tmp_path)


def test_next_schedule_uses_kst_calendar():
    assert next_schedule(datetime.fromisoformat('2026-10-03T14:00:00+09:00'))=='2026-10-04T07:30:00+09:00'


def test_operation_status_does_not_label_fx_as_an_investable_close(tmp_path):
    initialize(tmp_path)
    with sqlite3.connect(tmp_path/'portfolio_design.db') as db:
        db.execute("INSERT INTO prices_daily VALUES ('us_equity','2026-10-02',100,'test')")
        db.execute("INSERT INTO prices_daily VALUES ('__FX__','2026-10-05',1400,'test')")
    assert ledger_summary(tmp_path)['latest_price_date']=='2026-10-02'


def test_disposable_api_daily_same_db_preserves_records_and_skips_duplicate(tmp_path,monkeypatch):
    initialize(tmp_path)
    credentials=(tmp_path/'accounts.json').read_bytes()
    for key,value in environment(tmp_path).items():monkeypatch.setenv(key,value)
    from src.api.dependencies import reset_session_factory
    from src.api.design_workspace import _factory
    reset_session_factory();_factory.cache_clear()
    from src.api.main import app
    from src.api.services import _common as common
    from fastapi.testclient import TestClient
    accounts=json.loads(credentials)['accounts']
    account=accounts[0]
    from src.forward import competition
    monkeypatch.setattr(competition,'now_kst',lambda:datetime.fromisoformat('2026-09-30T12:00:00+09:00'))
    class Provider:
        def get_price_history(self,ticker,start,end):
            return pd.Series([100.,102.],index=pd.to_datetime(['2026-10-01','2026-10-02']))
    monkeypatch.setattr('src.forward.prices.get_default_provider',lambda:Provider())
    monkeypatch.setattr('src.forward.market_hours.guard_message',lambda:None)
    from datetime import date
    monkeypatch.setattr('src.forward.runtime.kst_today',lambda:date(2026,10,5))
    try:
        with TestClient(app) as client:
            assert client.post('/api/v1/auth/login',json={k:account[k] for k in ('email','password')}).status_code==200
            f=client.get('/api/v1/me/frontier').json()
            # Backdated confirmation exists ONLY in this disposable test, never
            # in the user's ongoing local operation database.
            monkeypatch.setattr(common,'now_utc',lambda:datetime.fromisoformat('2026-09-30T03:00:00+00:00'))
            r=client.post('/api/v1/me/onboarding/complete',headers={'X-CSRF-Token':client.cookies['ra_csrf']},
                json={'frontier_id':f['benchmark_frontier_id'],'theme_ids':[],'reason':'DISPOSABLE TEST ONLY'})
            assert r.status_code==200,r.text
            decision=client.get('/api/v1/me/decisions').json()['items'][0]
            # An individual confirmation no longer starts a cohort by itself.
            from src.forward.run_daily import main
            assert main([])==0
            with sqlite3.connect(tmp_path/'portfolio_design.db') as db:
                assert [db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('orders','trades','holdings_daily','nav_daily')]==[0,0,0,0]
            for person in accounts[1:]:
                assert client.post('/api/v1/auth/login',json={k:person[k] for k in ('email','password')}).status_code==200
                response=client.post('/api/v1/me/onboarding/complete',headers={'X-CSRF-Token':client.cookies['ra_csrf']},
                    json={'frontier_id':f['benchmark_frontier_id'],'theme_ids':[],'reason':'DISPOSABLE TEST ONLY'})
                assert response.status_code==200,response.text
            with sqlite3.connect(tmp_path/'portfolio_design.db') as db:
                db.row_factory=sqlite3.Row
                competition.schedule_start(db,'2026-10-01')
            monkeypatch.setattr(competition,'now_kst',lambda:datetime.fromisoformat('2026-10-03T12:00:00+09:00'))
            assert client.post('/api/v1/auth/login',json={k:account[k] for k in ('email','password')}).status_code==200
            monkeypatch.setattr(common,'now_utc',lambda:datetime.fromisoformat('2026-10-03T03:00:00+00:00'))
            assert main([])==0
            ledger=client.get('/api/v1/me/performance/ledger').json()
            assert ledger['snapshots'] and ledger['trades']
            for nav in ledger['snapshots']:
                assert nav['date'] >= decision['target_effective_date']
                assert nav['nav']==pytest.approx(nav['cash_balance']+sum(h['market_value'] for h in nav['holdings']))
            with sqlite3.connect(tmp_path/'portfolio_design.db') as db:
                counts=[db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('orders','trades','nav_daily','prices_daily')]
            assert main([])==0
            with sqlite3.connect(tmp_path/'portfolio_design.db') as db:
                assert counts==[db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('orders','trades','nav_daily','prices_daily')]
                # Personal fills exist, but CORE initial orders dated 10/5 still
                # wait for a post-effective close. PARTIAL must not consume the slot.
                assert db.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE status='success'").fetchone()[0]==0
                assert db.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE status='skipped'").fetchone()[0]==3
                latest=json.loads(db.execute("SELECT stats_json FROM scheduled_jobs ORDER BY started_at DESC LIMIT 1").fetchone()[0])
                assert latest['outcome']=='PARTIAL' and latest['retryable']
                # A newly available close belongs ONLY to this disposable fixture.
                for asset,price in db.execute("SELECT asset_id,price FROM prices_daily WHERE date='2026-10-02'").fetchall():
                    db.execute("INSERT INTO prices_daily VALUES (?,'2026-10-05',?,'SYNTHETIC_TEST')",(asset,price))
            assert main(['--use-stored-prices'])==0
            with sqlite3.connect(tmp_path/'portfolio_design.db') as db:
                assert db.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE status='success'").fetchone()[0]==1
                counts=[db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('orders','trades','nav_daily','prices_daily')]
            assert main(['--use-stored-prices'])==0
            with sqlite3.connect(tmp_path/'portfolio_design.db') as db:
                assert counts==[db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('orders','trades','nav_daily','prices_daily')]
                assert db.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE status='skipped'").fetchone()[0]==4
            ledger=client.get('/api/v1/me/performance/ledger').json()
            with sqlite3.connect(tmp_path/'capstone_demo.db') as db:
                assert db.execute('SELECT COUNT(*) FROM scheduled_jobs').fetchone()[0]==0
        initialize(tmp_path)
        assert (tmp_path/'accounts.json').read_bytes()==credentials
        reset_session_factory();_factory.cache_clear()
        with TestClient(app) as restarted:
            assert restarted.post('/api/v1/auth/login',json={k:account[k] for k in ('email','password')}).status_code==200
            assert restarted.get('/api/v1/me/decisions').json()['items'][0]==decision
            assert restarted.get('/api/v1/me/performance/ledger').json()['snapshots']==ledger['snapshots']
    finally:
        reset_session_factory();_factory.cache_clear()
