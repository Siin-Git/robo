"""Disposable counterfactual ledgers; all prices below are synthetic TEST inputs."""
from datetime import date, datetime, timedelta
import json
import shutil
import sqlite3
import secrets
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from scripts.competition_replay import environment, prepare
from src.api.dependencies import reset_session_factory
from src.api.design_workspace import _factory
from src.api.main import app
from src.db.base import Base
from src.forward import competition as gate, replay
from src.forward.config import load_forward_config
from src.forward.run_daily import _execute_daily
from src.local.capstone import EMAILS
from src.local.lab_meeting import prepare as prepare_roster


@pytest.fixture
def lab(tmp_path, monkeypatch):
    directory = tmp_path / "isolated-replay"
    directory.mkdir()
    (directory / "local-replay.json").write_text(json.dumps({"kind":"LOCAL_COMPETITION_REPLAY"}))
    env = {"APP_PROFILE":"local", "CAPSTONE_DEMO":"1", "CAPSTONE_MARKET_COMPARISON":"1",
           "DATABASE_BACKEND":"sqlite", "CAPSTONE_DATA_DIR":str(directory),
           "DATABASE_URL":"", "CAPSTONE_DESIGN_DATABASE_URL":"", "AUTH_COOKIE_SECURE":"false",
           "ALLOW_PUBLIC_REGISTRATION":"false", "DESIGN_PRICE_SOURCE":"",
           "CAPSTONE_LAB_ACCOUNTS_JSON":"", "CAPSTONE_INVITATIONS_JSON":"", "TZ":"Asia/Seoul"}
    (directory / "environment.json").write_text(json.dumps(env))
    for key, value in {**env, "COMPETITION_REPLAY_DIR":str(directory)}.items():
        monkeypatch.setenv(key, value)
    reset_session_factory(); _factory.cache_clear()
    accounts = [{"email":email, "password":secrets.token_urlsafe(24)} for email in EMAILS]
    (directory / "accounts.json").write_text(json.dumps({"accounts":accounts}))
    engine = create_engine(f"sqlite:///{directory/'capstone_demo.db'}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        prepare_roster(db, "replay-test", {a["email"]:a["password"] for a in accounts})
        db.commit()
    from src.forward.prices import CORE_IDS
    assets = [*CORE_IDS, *["theme:"+t for t in ("ai","robotics","nuclear","power_grid","cybersecurity","cloud_data_center")], "__FX__"]
    days = [d.date().isoformat() for d in pd.bdate_range(end=date.today()-timedelta(days=3), periods=12)]
    # One source gap proves selection/exclusion; never used by the actual demo.
    prices = {a:{d:100+i+j*.25+(-1)**j for j,d in enumerate(days)} for i,a in enumerate(assets)}
    del prices["__FX__"][days[5]]
    (directory / "market-prices.json").write_text(json.dumps({"kind":"REAL_MARKET_PRICES",
        "provider":"TEST_FIXTURE_DO_NOT_PRESENT_AS_MARKET", "retrieved_at":"test-only",
        "tickers":{a:a for a in assets}, "prices":prices}))
    run = prepare(directory)
    con = sqlite3.connect(directory / "replay_ledger.db"); con.row_factory=sqlite3.Row
    with TestClient(app) as client:
        def login(index=0):
            client.cookies.clear()
            assert client.post("/api/v1/auth/login", json=accounts[index]).status_code == 200
        login()
        yield SimpleNamespace(directory=directory, con=con, client=client, login=login, run=run, accounts=accounts)
    con.close(); engine.dispose(); reset_session_factory(); _factory.cache_clear()


def counts(con):
    return tuple(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("orders","trades","holdings_daily","nav_daily","portfolio_targets"))


def test_full_15_engine_accounting_api_consistency_and_no_actual_history(lab):
    x=lab
    assert replay.execute(x.directory)["completed"] == 15
    assert replay.verify_completed(x.con,x.run) == 15
    assert len(x.run["dates"]) == 10 and x.run["excluded_dates"]
    assert x.con.execute("SELECT COUNT(*) FROM nav_daily").fetchone()[0] == 300
    assert x.con.execute("SELECT COUNT(DISTINCT initial_capital_krw) FROM accounts").fetchone()[0] == 1
    original=x.con.execute("SELECT confirmed_at,effective_date FROM portfolio_decisions").fetchall()
    assert all(str(r[1]) > x.run["end"] for r in original)
    for i in range(15):
        x.login(i)
        own=x.client.get('/api/v1/me/performance/dashboard?comparison=common').json()
        comp=x.client.get('/api/v1/me/performance/comparison').json()
        contribution=x.client.get('/api/v1/me/performance/contributions?comparison=common').json()
        pid=x.client.get('/api/v1/me').json()['participant_id']
        mine=next(r for r in comp['items'] if r['participant_id']==pid)
        assert comp['ranked']==15 and comp['replay_context']['completed']==15
        assert (own['start'],own['end'])==(x.run['start'],x.run['end'])
        assert own['metrics']==mine['metrics']
        assert contribution['cumulative_return']==pytest.approx(own['metrics']['cumulative_return'])
        assert contribution['reconciliation']['reconciled']
        assert own['observations']==10 and own['metrics']['volatility'] is None
        assert mine['metric_quality']['mdd']['reason']=='OBSERVATION_GAPS'
    assert x.client.get('/api/v1/me/performance/comparison?basis=mdd').json()['ranked']==0
    old=counts(x.con)
    assert replay.execute(x.directory)['reused']
    assert prepare(x.directory)['run_id']==x.run['run_id']
    assert counts(x.con)==old
    # Review uses the actual design DB, not the counterfactual valuations.
    decision=x.run['members'][-1]['decision_id']
    review=x.client.get(f'/api/v1/me/decisions/{decision}/review')
    assert review.status_code==200
    with sqlite3.connect(x.directory/'portfolio_design.db') as source:
        assert counts(source)[:4] == (0,0,0,0)
        assert source.execute("SELECT value FROM forward_state WHERE key='competition_start'").fetchone() is None
        assert [tuple(r) for r in original]==source.execute("SELECT confirmed_at,effective_date FROM portfolio_decisions").fetchall()
    # Owner-only ledger: another participant cannot request private details.
    other=x.run['members'][0]['participant_id']
    assert x.client.get(f'/api/v1/participants/{other}/performance/ledger').status_code==403


def test_failure_after_fills_before_checkpoint_resumes_without_second_initial_buy(lab,monkeypatch):
    from src.forward import ledger
    real=ledger.valuate
    def interrupt(*args,**kwargs):
        raise RuntimeError('TEST interruption after committed fills')
    monkeypatch.setattr(ledger,'valuate',interrupt)
    with pytest.raises(RuntimeError,match='interruption'):
        replay.execute(lab.directory)
    before=counts(lab.con)
    assert before[0]>0 and before[1]>0 and before[3]==0
    partial=lab.client.get('/api/v1/me/performance/comparison').json()
    assert partial['reason']=='REPLAY_INCOMPLETE' and partial['ranked']==0
    assert all(row['rank'] is None for row in partial['items'])
    monkeypatch.setattr(ledger,'valuate',real)
    replay.execute(lab.directory)
    aid=lab.run['members'][0]['account_ids'][0]
    assert lab.con.execute('SELECT COUNT(*) FROM orders WHERE account_id=?',(aid,)).fetchone()[0]==before[0]
    assert lab.con.execute('SELECT COUNT(*) FROM trades WHERE account_id=?',(aid,)).fetchone()[0]==before[1]
    after=counts(lab.con); replay.execute(lab.directory)
    assert counts(lab.con)==after


def test_checkpoint_resume_missing_price_and_daily_fail_closed(lab,monkeypatch):
    with pytest.raises(RuntimeError,match='Injected'):
        replay.execute(lab.directory,fail_after=1)
    assert lab.client.get('/api/v1/me/performance/replay').json()['replay_context']['completed']==0
    assert lab.client.get('/api/v1/me/performance/comparison').json()['ranked']==0
    monkeypatch.setattr('src.forward.prices.refresh_live',lambda *a:pytest.fail('daily must not refresh the replay DB'))
    old=counts(lab.con)
    assert _execute_daily(lab.con,load_forward_config(),date.today().isoformat())[1]['reason']=='REPLAY_SCOPED_EXECUTION_REQUIRED'
    assert counts(lab.con)==old
    with replay.exclusive(lab.directory), pytest.raises(RuntimeError,match='already executing'):
        replay.execute(lab.directory)
    replay.execute(lab.directory)
    complete_counts=counts(lab.con)
    aid=next(a for a,w in lab.run['weights'].items() if w.get('us_equity',0)>0)
    price=lab.con.execute("SELECT * FROM prices_daily WHERE asset_id='us_equity' AND date=?",(lab.run['end'],)).fetchone()
    lab.con.execute("DELETE FROM prices_daily WHERE asset_id='us_equity' AND date=?",(lab.run['end'],))
    lab.con.commit()
    replay.save_state(lab.con,'replay_progress:'+aid,lab.run['dates'][-2])
    replay.save_state(lab.con,'replay_status','INCOMPLETE')
    with pytest.raises(RuntimeError,match='us_equity'):
        replay.execute(lab.directory)
    assert lab.client.get('/api/v1/me/performance/comparison').json()['ranked']==0
    lab.con.execute('INSERT INTO prices_daily VALUES (?,?,?,?)',tuple(price));lab.con.commit()
    replay.execute(lab.directory)
    assert counts(lab.con)==complete_counts
    assert replay.verify_completed(lab.con,lab.run)==15


def test_forward_transition_only_on_completed_copy_keeps_initial_orders(lab,monkeypatch,tmp_path):
    replay.execute(lab.directory)
    copy=tmp_path/'forward-validation'
    shutil.copytree(lab.directory,copy)
    marker={'kind':'LOCAL_COMPETITION_REPLAY','forward_validation_copy':True}
    (copy/'local-replay.json').write_text(json.dumps(marker))
    env=json.loads((copy/'environment.json').read_text());env['CAPSTONE_DATA_DIR']=str(copy)
    (copy/'environment.json').write_text(json.dumps(env))
    for k,v in {**env,'COMPETITION_REPLAY_DIR':str(copy)}.items():monkeypatch.setenv(k,v)
    reset_session_factory()
    with sqlite3.connect(copy/'replay_ledger.db') as con:
        con.row_factory=sqlite3.Row
        before=counts(con); forward=lab.run['forward_start']
        monkeypatch.setattr(gate,'now_kst',lambda:datetime.fromisoformat(forward+'T08:00:00+09:00'))
        for row in con.execute('SELECT asset_id,price FROM prices_daily WHERE date=?',(lab.run['end'],)).fetchall():
            con.execute('INSERT INTO prices_daily VALUES (?,?,?,?)',(row['asset_id'],forward,row['price'],'SYNTHETIC_TEST_FORWARD'))
        con.commit()
        monkeypatch.setattr('src.forward.prices.refresh_live',lambda *a:{'asof':forward,'new_points':0,'stale':[]})
        monkeypatch.setattr('src.forward.run_daily.load_or_build_cov',lambda *a:(pd.DataFrame(),{}))
        with replay.execution_scope(con,'FORWARD_VALIDATION'):
            assert gate.policy(con)['status']=='STARTED'
            code,stats=_execute_daily(con,load_forward_config(),forward)
            assert code==0 and stats['status']=='PASS'
            first=counts(con)
            _execute_daily(con,load_forward_config(),forward)
            assert counts(con)==first
        assert first[:2]==before[:2] and first[3]==before[3]+30
        assert replay.state(con,'first_execution_at') is None  # replay fills are not real-forward inception
        assert replay.verify_completed(con,lab.run)==15
    assert counts(lab.con)==before


def test_corrupt_coverage_and_changed_manifest_never_claim_complete(lab):
    replay.execute(lab.directory)
    lab.con.execute('DELETE FROM nav_daily WHERE account_id=? AND date=?',
                    (lab.run['members'][0]['account_ids'][0],lab.run['dates'][4]));lab.con.commit()
    meta=lab.client.get('/api/v1/me/performance/replay').json()['replay_context']
    assert meta['status']=='INCOMPLETE' and meta['completed']==14
    assert lab.client.get('/api/v1/me/performance/comparison').json()['ranked']==0
    with pytest.raises(RuntimeError,match='incomplete'):
        replay.execute(lab.directory)
    path=lab.directory/'run.json';path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='manifest changed'):
        replay.execute(lab.directory)


def test_preparation_interruption_resumes_only_its_empty_marked_copy(lab,monkeypatch):
    # Preparation itself can be restarted without changing the source decisions.
    x=lab
    (x.directory/'run.json').unlink()
    with pytest.raises(ValueError,match='Unmarked'):
        prepare(x.directory)
    journal=x.directory/'preparing.json'
    journal.write_text(json.dumps({'kind':'LOCAL_REPLAY_PREPARATION','directory':str(x.directory)}))
    from src.forward import prices
    real=prices.upsert_prices
    monkeypatch.setattr(prices,'upsert_prices',lambda *a:(_ for _ in ()).throw(RuntimeError('TEST preparation interruption')))
    with pytest.raises(RuntimeError,match='preparation interruption'):
        prepare(x.directory)
    assert journal.exists() and not (x.directory/'run.json').exists()
    monkeypatch.setattr(prices,'upsert_prices',real)
    resumed=prepare(x.directory)
    assert resumed['required']==15 and not journal.exists()
    assert replay.execute(x.directory)['completed']==15


def test_daily_dry_run_reports_ready_without_mutation(lab,capsys):
    from src.forward.run_daily import _dry_run_daily
    before=counts(lab.con)
    assert _dry_run_daily(lab.con,load_forward_config(),date.today().isoformat())==0
    assert 'REPLAY_SCOPED_EXECUTION_REQUIRED' in capsys.readouterr().out
    assert counts(lab.con)==before
