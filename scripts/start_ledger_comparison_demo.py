"""Extend the existing disposable Monday launcher with 0/1/multiple ledger rows.

TEST_FIXTURE only. Guard, private accounts, fixed clock and server lifecycle are
owned by start_monday_demo; this never opens an operating database.
"""
from datetime import date, datetime
import json

import start_monday_demo as monday

prepare_monday = monday.prepare


def prepare(directory, environment):
    prepare_monday(directory, environment)
    from fastapi.testclient import TestClient
    import sqlite3
    from src.api.main import app
    from src.api.services import _common as C
    from src.forward.execution import create_orders, execute_pending
    from src.forward.ledger import valuate
    from src.forward.accounts import versions_from_cfg
    from src.forward.config import load_forward_config
    accounts = json.loads((directory/'accounts.json').read_text())['accounts']
    cases = []
    with TestClient(app) as client:
        for index, confirmed_at, values in [
            (0, None, [('2026-10-05',103)]),
            (2, '2026-10-01T03:00:00+00:00', [('2026-10-05',103)]),
            (3, '2026-10-01T03:00:00+00:00', [('2026-10-02',101),('2026-10-05',103)]),
            (5, '2026-10-01T03:00:00+00:00', []),
        ]:
            client.cookies.clear()
            C.now_utc = lambda: datetime.fromisoformat(monday.MONDAY)
            a = accounts[index]
            assert client.post('/api/v1/auth/login',json={'email':a['email'],'password':a['password']}).status_code == 200
            if confirmed_at:
                C.now_utc = lambda: datetime.fromisoformat(confirmed_at)
                f = client.get('/api/v1/me/frontier').json()
                result=client.post('/api/v1/me/onboarding/complete',headers={'X-CSRF-Token':client.cookies['ra_csrf']},
                    json={'frontier_id':f['benchmark_frontier_id'],'theme_ids':[], 'reason':'SYNTHETIC ledger comparison regression fixture'})
                assert result.status_code == 200
            C.now_utc = lambda: datetime.fromisoformat(monday.MONDAY)
            pid = client.get('/api/v1/me').json()['participant_id']
            cfg=load_forward_config();ft=cfg['forward_test'];versions=versions_from_cfg(cfg)
            con=sqlite3.connect(directory/'portfolio_design.db');con.row_factory=sqlite3.Row
            try:
                for account in con.execute('SELECT account_id FROM accounts WHERE participant_id=?',(pid,)).fetchall():
                    aid=account['account_id']
                    for day, price in values:
                        target=con.execute('SELECT weights_json,created_at,effective_date FROM portfolio_targets WHERE account_id=? AND effective_date<=? ORDER BY effective_date DESC,created_at DESC LIMIT 1',(aid,day)).fetchone()
                        assert target is not None
                        weights=json.loads(target['weights_json'])
                        for asset in weights:
                            if asset!='cash':
                                con.execute('INSERT OR REPLACE INTO prices_daily VALUES (?,?,?,?)',(asset,day,price,'SYNTHETIC_TEST_COMPARISON'))
                        con.commit()
                        if not con.execute('SELECT 1 FROM trades WHERE account_id=? LIMIT 1',(aid,)).fetchone():
                            create_orders(con,aid,weights,target['created_at'],target['effective_date'],ft['benchmark_version'],pid,baseline={})
                            execute_pending(con,aid,day,float(ft['costs']['trading_cost_bps']),ft['benchmark_version'],pid)
                        outcome=valuate(con,aid,day,versions,float(ft['initial_capital_krw']))
                        assert outcome['status']!='NAV_INCOMPLETE'
                con.commit()
            finally:
                con.close()
            cases.append({'account_index':index,'participant_id':pid})
    (directory/'ledger-comparison-fixture.json').write_text(json.dumps({
        'data_kind':'TEST_FIXTURE','clock':monday.MONDAY,'cases':cases},indent=2))


if __name__=='__main__':
    monday.prepare=prepare
    monday.main()
