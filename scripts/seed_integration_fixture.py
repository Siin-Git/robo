"""Synthetic browser fixture, restricted to a disposable local SQLite design DB."""
import argparse,json,sys,sqlite3
from pathlib import Path
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def main():
    p=argparse.ArgumentParser();p.add_argument('--database',type=Path,required=True);p.add_argument('--account',required=True);a=p.parse_args();path=a.database.resolve()
    if not (path.is_relative_to(Path('/private/tmp')) or path.is_relative_to(ROOT/'.work')) or path.name!='portfolio_design.db':p.error('Only an isolated test design DB is allowed.')
    con=sqlite3.connect(path);con.row_factory=sqlite3.Row
    from src.forward.decision_policy import latest_decision
    d=latest_decision(con,a.account)
    if not d or con.execute('SELECT trade_id FROM trades WHERE account_id=? LIMIT 1',(a.account,)).fetchone():p.error('Require confirmed test decision with no existing trades; never overwrite history.')
    from src.forward.execution import create_orders,execute_pending
    from src.forward.ledger import valuate
    from src.forward.accounts import versions_from_cfg
    from src.forward.config import load_forward_config
    cfg=load_forward_config();v=versions_from_cfg(cfg);ft=cfg['forward_test'];pid=d['participant_id'];start=date.fromisoformat(d['effective_date'])
    accounts=con.execute('SELECT account_id FROM accounts WHERE participant_id=?',(pid,)).fetchall()
    for i in range(4):
        day=start+timedelta(days=i)
        if day.weekday()>=5:continue
        for account in accounts:
            aid=account['account_id'];t=con.execute('SELECT weights_json FROM portfolio_targets WHERE account_id=? ORDER BY effective_date DESC,created_at DESC,target_id DESC LIMIT 1',(aid,)).fetchone();w=json.loads(t[0])
            for asset in w:
                if asset!='cash':con.execute('INSERT OR REPLACE INTO prices_daily VALUES (?,?,?,?)',(asset,str(day),100+i,'SYNTHETIC_TEST'))
            con.commit()
            if i==0:create_orders(con,aid,w,d['confirmed_at'],str(start),ft['benchmark_version'],pid,baseline={})
            execute_pending(con,aid,str(day),float(ft['costs']['trading_cost_bps']),ft['benchmark_version'],pid)
            valuate(con,aid,str(day),v,float(ft['initial_capital_krw']))
    con.close();print('TEST_FIXTURE only; synthetic results are not operational history.')
if __name__=='__main__':main()
