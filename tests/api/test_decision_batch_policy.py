"""Synthetic prices in disposable fixtures; never operational history."""
from datetime import date
import sqlite3
import json
import numpy as np
import pandas as pd
import pytest
from .test_decisions import identity, confirm
from src.forward.config import load_forward_config
from src.forward.run_daily import _execute_daily
from src.forward.run_weekly import _execute_weekly
from src.forward.run_monthly import _execute_monthly
from src.db.models import Account, PriceDaily
from sqlalchemy import select


def test_no_preconfirmation_execution_keep_preserves_composition_and_repeat_is_safe(client,env,identity,monkeypatch):
    monkeypatch.setenv('CAPSTONE_DEMO','1');monkeypatch.setenv('APP_PROFILE','local')
    # Match the API dependency override: this isolated legacy fixture has no
    # active competition cohort. Never read a developer's real auth database.
    monkeypatch.setattr('src.forward.competition.get_database_url', lambda: f'sqlite:///{env.dbfile}')
    # Direct fixture DB, not the API's routed design store or an external DB.
    from src.api.services import onboarding_service
    cookies,_=identity
    pid=client.get('/api/v1/auth/me',cookies=cookies).json()['participant_id']
    cfg=load_forward_config()
    con=sqlite3.connect(env.dbfile);con.row_factory=sqlite3.Row
    ids=['us_equity','developed_ex_us','emerging_markets','korea_equity','us_treasury','korea_treasury','tips','gold','global_reit','theme:ai']
    with env.factory() as s:
        for aid in ids:s.add(PriceDaily(asset_id=aid,date=date(2026,10,2),price=100,source='SYNTHETIC_TEST'))
        s.commit()
    monkeypatch.setattr('src.forward.prices.refresh_live',lambda *a:{'asof':'2026-10-02','new_points':0,'stale':[]})
    cov=pd.DataFrame(np.eye(len(ids))*.01,index=ids,columns=ids)
    monkeypatch.setattr('src.forward.run_daily.load_or_build_cov',lambda *a:(cov,{}))
    monkeypatch.setattr('src.forward.run_weekly.load_or_build_cov',lambda *a:(cov,{}))
    monkeypatch.setattr('src.forward.run_monthly.rebuild_cov',lambda *a:(cov,{}))
    # No final decision -> neither personal nor participant core may trade or value.
    _execute_daily(con,cfg,'2026-10-03')
    assert con.execute('SELECT COUNT(*) FROM orders').fetchone()[0]==0
    assert con.execute('SELECT COUNT(*) FROM nav_daily').fetchone()[0]==0
    with env.factory() as s:
        uid=s.scalar(select(__import__('src.db.models',fromlist=['User']).User.user_id))
        from src.api.services.frontier_service import get_frontier
        result=onboarding_service.complete(s,uid,pid,get_frontier()['benchmark_frontier_id'],['ai'],'confirmed')
        s.commit()
        from src.api.services.decision_service import latest,choose
        personal=s.scalar(select(Account).where(Account.account_type=='personal'))
        account_id=personal.account_id
        d=latest(s,account_id);snapshot=dict(d.weights_json);eff=d.effective_date
        choose(s,uid,d.decision_id,d.target_id,'KEEP','retain final composition','keep-batch-001');s.commit()
    _execute_daily(con,cfg,'2026-10-03')
    assert con.execute('SELECT COUNT(*) FROM trades').fetchone()[0]==0
    assert con.execute('SELECT COUNT(*) FROM nav_daily').fetchone()[0]==0
    for aid in ids:con.execute('INSERT INTO prices_daily VALUES (?,?,?,?)',(aid,str(eff),101,'SYNTHETIC_TEST'))
    con.commit()
    monkeypatch.setattr('src.forward.prices.refresh_live',lambda *a:{'asof':str(eff),'new_points':0,'stale':[]})
    _execute_daily(con,cfg,str(eff));n=con.execute('SELECT COUNT(*) FROM trades').fetchone()[0];assert n>0
    _execute_daily(con,cfg,str(eff));assert con.execute('SELECT COUNT(*) FROM trades').fetchone()[0]==n
    assert con.execute('SELECT MIN(execution_at) FROM trades').fetchone()[0]>=str(eff)
    _execute_weekly(con,cfg,'2026-10-09')
    _execute_monthly(con,cfg,'2026','10','2026-10-31',False)
    target=con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id=? ORDER BY effective_date DESC LIMIT 1",(account_id,)).fetchone()
    assert json.loads(target[0])==snapshot
    nav=con.execute('SELECT nav,cash_balance FROM nav_daily WHERE account_id=?',(account_id,)).fetchone()
    holdings=con.execute('SELECT SUM(market_value) FROM holdings_daily WHERE account_id=?',(account_id,)).fetchone()[0]
    assert float(nav['nav'])==pytest.approx(float(nav['cash_balance'])+float(holdings))
    con.close()
