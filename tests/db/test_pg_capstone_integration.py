"""Real isolated PostgreSQL: two databases, decision/choice invariants and job claims."""
import os
from datetime import date, datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import subprocess, sys
import pytest
from sqlalchemy import create_engine, select, text, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DatabaseError

AUTH=os.environ.get('TEST_AUTH_DATABASE_URL')
DESIGN=os.environ.get('TEST_DESIGN_DATABASE_URL')
pytestmark=pytest.mark.skipif(not (AUTH and DESIGN),reason='isolated TEST_AUTH_DATABASE_URL / TEST_DESIGN_DATABASE_URL not set')

def test_real_pg_split_immutability_ownership_choices_batch_and_dedup(monkeypatch):
    from src.db.models import Theme, User, PortfolioDecision, PortfolioChoice, PriceDaily, Account
    from src.api.services import auth_service, decision_service
    from src.api.dependencies import get_db
    from src.api.main import app
    from fastapi.testclient import TestClient
    for url in (AUTH,DESIGN):
        e=dict(os.environ,DATABASE_URL=url,DATABASE_BACKEND='postgres');e.pop('CAPSTONE_DEMO',None);e.pop('CAPSTONE_DESIGN_DATABASE_URL',None)
        r=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=e,capture_output=True,text=True)
        assert r.returncode==0,r.stderr
    for k,v in dict(APP_PROFILE='local',CAPSTONE_DEMO='1',DATABASE_BACKEND='postgres',DATABASE_URL=AUTH,CAPSTONE_DESIGN_DATABASE_URL=DESIGN,AUTH_COOKIE_SECURE='false',DESIGN_PRICE_SOURCE='/tmp/absent-pg-fixture-source').items():monkeypatch.setenv(k,v)
    a=create_engine(AUTH);b=create_engine(DESIGN);af=sessionmaker(a);bf=sessionmaker(b)
    suffix=uuid4().hex[:8];password='Isolated-local-pg-test-12345';users=[]
    with af() as s:
        if not s.get(Theme,'ai'):s.add(Theme(theme_id='ai',display_name='AI',theme_type='theme',ticker='AIQ',market='US',currency='USD',active=True,valid_from=date(2026,1,1),universe_version='THEME_UNIVERSE_V0.1'))
        for i in range(2):
            u=auth_service.register(s,f'pg-{suffix}-{i}@example.com',password,'PG fixture')
            users.append((u['user_id'],u['email']))
        s.commit()
    def db():
        with af() as s:
            try:yield s;s.commit()
            except Exception:s.rollback();raise
    app.dependency_overrides[get_db]=db
    try:
        with TestClient(app) as c:
            login=c.post('/api/v1/auth/login',json={'email':users[0][1],'password':password});assert login.status_code==200,login.text
            h={'X-CSRF-Token':c.cookies['ra_csrf']}
            frontier=c.get('/api/v1/me/frontier').json()
            r=c.post('/api/v1/me/onboarding/complete',headers=h,json={'frontier_id':frontier['benchmark_frontier_id'],'theme_ids':['ai'],'reason':'PG final'})
            assert r.status_code==200,r.text
            d=c.get('/api/v1/me/decisions').json()['items'][0]
            assert c.get(f"/api/v1/me/decisions/{d['decision_id']}/review").status_code==200
            c.post('/api/v1/auth/login',json={'email':users[1][1],'password':password})
            assert c.get(f"/api/v1/me/decisions/{d['decision_id']}/review").status_code==404
        with af() as s:assert s.scalar(select(func.count()).select_from(PortfolioDecision))==0
        with bf() as s:
            snap=s.get(PortfolioDecision,d['decision_id']);assert snap.confirmed_at.tzinfo and isinstance(snap.weights_json,dict)
            assert snap.provenance_json['internal_tracking']['capture']=='AT_CONFIRMATION'
            assert 'internal_tracking' not in d['provenance']
            with pytest.raises(DatabaseError):s.execute(text('UPDATE portfolio_decisions SET version=999 WHERE decision_id=:id'),{'id':d['decision_id']})
            s.rollback()
            with pytest.raises(DatabaseError):s.execute(text('DELETE FROM portfolio_decisions WHERE decision_id=:id'),{'id':d['decision_id']})
            s.rollback()
        def repeat(_):
            with bf() as s:
                result=decision_service.choose(s,users[0][0],d['decision_id'],d['target_id'],'KEEP','same request',f'pg-keep-{suffix}');s.commit();return result['choice_id']
        with ThreadPoolExecutor(max_workers=4) as pool:assert len(set(pool.map(repeat,range(4))))==1
        # Internal audit notes serialize on the same account without modifying
        # the immutable decision or allocating customer orders/choices.
        from src.api.services import internal_tracking_service as tracking
        def review_repeat(_):
            with bf() as s:
                note=tracking.record_review(s,'ISOLATED_ADMIN',d['decision_id'],'theme:ai',
                    'KEEP_OBSERVING','PG fixture observations only',f'pg-review-{suffix}')
                s.commit();return note['review_id']
        with ThreadPoolExecutor(max_workers=4) as pool:assert len(set(pool.map(review_repeat,range(4))))==1
        with bf() as s:
            report=tracking.report(s,d['decision_id'])
            assert len(report['reviews'])==1 and report['visibility']=='ADMIN_ONLY'
            assert report['reviews'][0]['changes_model_or_orders'] is False
        # API, stdlib-like engine and job registry resolve exactly the design DB.
        from src.forward.db import connect
        from src.forward.decision_policy import latest_decision, weights
        con=connect('/tmp/ignored-pg-path')
        assert latest_decision(con,d['account_id'])['decision_id']==d['decision_id']
        assert con.execute('SELECT COUNT(*) c FROM portfolio_choices').fetchone()['c']>=1
        from src.forward.execution import create_orders,execute_pending
        from src.forward.ledger import valuate
        from src.forward.accounts import versions_from_cfg
        from src.forward.config import load_forward_config
        cfg=load_forward_config();v=versions_from_cfg(cfg);w=d['weights'];day=d['target_effective_date']
        for aid in w:
            if aid!='cash':con.execute('INSERT INTO prices_daily(asset_id,date,price,source) VALUES (?,?,?,?) ON CONFLICT(asset_id,date) DO NOTHING',(aid,day,100,'SYNTHETIC_TEST'))
        con.commit()
        create_orders(con,d['account_id'],w,d['confirmed_at'],day,v['benchmark_version'],d['participant_id'],baseline={})
        assert execute_pending(con,d['account_id'],'2026-10-03',5,v['benchmark_version'])==[]
        tids=execute_pending(con,d['account_id'],day,5,v['benchmark_version']);assert tids
        assert execute_pending(con,d['account_id'],day,5,v['benchmark_version'])==[]
        assert valuate(con,d['account_id'],day,v,100000000)['status']=='OK'
        n=con.execute('SELECT nav,cash_balance FROM nav_daily WHERE account_id=?',(d['account_id'],)).fetchone()
        hv=con.execute('SELECT SUM(market_value) m FROM holdings_daily WHERE account_id=?',(d['account_id'],)).fetchone()['m']
        assert n['nav']==pytest.approx(n['cash_balance']+hv)
        con.close()
        from src.forward import jobs
        slot='2026-10-03';job_type=f'pg-{suffix}'
        def claim(_):return jobs.claim_job(None,job_type,slot,sqlite_path='/tmp/ignored')
        with ThreadPoolExecutor(max_workers=4) as pool:claims=list(pool.map(claim,range(4)))
        winners=[r for r in claims if r[1]=='run'];assert len(winners)==1,claims
        jobs.complete_job(None,winners[0][0],{'fixture':True},sqlite_path='/tmp/ignored')
        assert claim(0)[1]==claim(0)[1]=='skipped'
        with af() as s:assert s.scalar(select(func.count()).select_from(__import__('src.db.models',fromlist=['ScheduledJob']).ScheduledJob))==0
    finally:app.dependency_overrides.clear();a.dispose();b.dispose()
