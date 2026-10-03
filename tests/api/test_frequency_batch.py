"""Use the existing monthly engine against disposable user accounts only."""
from copy import deepcopy
from datetime import datetime, timezone
import sqlite3
import numpy as np
import pandas as pd
from .conftest import register, login
from src.api.services import _common as C
from src.forward.config import load_forward_config
from src.forward.run_monthly import _execute_monthly, _dry_run_monthly

def test_personal_frequency_overrides_global_gate_and_dry_run_matches(client,env,monkeypatch,tmp_path):
    monkeypatch.setenv('ALLOW_PUBLIC_REGISTRATION','true')
    monkeypatch.setattr(C,'now_utc',lambda:datetime(2026,9,1,tzinfo=timezone.utc))
    accounts={}
    for frequency in ('monthly','quarterly'):
        email=f'{frequency}@example.com'
        register(client,email); cookies=dict(login(client,email).cookies)
        headers={'X-CSRF-Token':cookies['ra_csrf']}
        fid=client.get('/api/v1/me/frontier',cookies=cookies).json()['benchmark_frontier_id']
        r=client.post('/api/v1/me/onboarding/complete',cookies=cookies,headers=headers,json={'frontier_id':fid,'theme_ids':['ai'],'rebalance_frequency':frequency})
        assert r.status_code==200,r.text
        accounts[frequency]=client.get('/api/v1/me/decisions',cookies=cookies).json()['items'][0]['account_id']
    cfg=deepcopy(load_forward_config());cfg['forward_test']['core_rebalance']['frequency']='quarterly'
    ids=['us_equity','developed_ex_us','emerging_markets','korea_equity','us_treasury','korea_treasury','tips','gold','global_reit','theme:ai']
    cov=pd.DataFrame(np.eye(len(ids))*.01,index=ids,columns=ids)
    monkeypatch.setattr('src.forward.run_monthly.rebuild_cov',lambda *a:(cov,{}))
    # Keep generated risk artifacts in this test directory.
    original_resolve=__import__('src.forward.config',fromlist=['resolve']).resolve
    monkeypatch.setattr('src.forward.config.resolve',lambda p:tmp_path/'risk.npz' if str(p).startswith('outputs/forward/') else original_resolve(p))
    with sqlite3.connect(env.dbfile) as con:
        con.row_factory=sqlite3.Row
        before=con.total_changes
        assert _dry_run_monthly(con,cfg,'2026','10','2026-10-31',False)==0
        assert con.total_changes==before
        code,stats=_execute_monthly(con,cfg,'2026','10','2026-10-31',False)
        assert code==0 and stats['rebalanced']
        ids_oct={r[0] for r in con.execute("SELECT account_id FROM portfolio_targets WHERE effective_date='2026-11-02'")}
        assert accounts['monthly'] in ids_oct and accounts['quarterly'] not in ids_oct
        code,_=_execute_monthly(con,cfg,'2026','12','2026-12-31',False)
        ids_dec={r[0] for r in con.execute("SELECT account_id FROM portfolio_targets WHERE effective_date='2027-01-01'")}
        assert accounts['monthly'] in ids_dec and accounts['quarterly'] in ids_dec
