"""Append known prices/fills/NAV only to the disposable comparison browser fixture."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args();directory=args.directory.resolve()
    marker=directory/'ledger-comparison-fixture.json'
    if not directory.is_relative_to(Path('/private/tmp')) or not marker.is_file():
        parser.error('Only an explicitly marked disposable comparison fixture is allowed.')
    fixture=json.loads(marker.read_text())
    if fixture.get('data_kind')!='TEST_FIXTURE': parser.error('Synthetic fixture required.')
    case=next(c for c in fixture['cases'] if c['account_index']==5)
    os.environ.update(DATABASE_BACKEND='sqlite',DATABASE_URL='',CAPSTONE_DESIGN_DATABASE_URL='')
    from src.forward.execution import create_orders,execute_pending
    from src.forward.ledger import valuate
    from src.forward.config import load_forward_config
    from src.forward.accounts import versions_from_cfg
    cfg=load_forward_config();ft=cfg['forward_test'];versions=versions_from_cfg(cfg)
    con=sqlite3.connect(directory/'portfolio_design.db');con.row_factory=sqlite3.Row
    try:
        for account in con.execute('SELECT account_id FROM accounts WHERE participant_id=?',(case['participant_id'],)).fetchall():
            aid=account['account_id']
            for day in ['2026-10-02','2026-10-05']:
                if con.execute('SELECT 1 FROM nav_daily WHERE account_id=? AND date=?',(aid,day)).fetchone(): continue
                target=con.execute('SELECT * FROM portfolio_targets WHERE account_id=? AND effective_date<=? ORDER BY effective_date DESC,created_at DESC LIMIT 1',(aid,day)).fetchone()
                assert target is not None
                if not con.execute('SELECT 1 FROM trades WHERE account_id=? LIMIT 1',(aid,)).fetchone():
                    create_orders(con,aid,json.loads(target['weights_json']),target['created_at'],target['effective_date'],ft['benchmark_version'],case['participant_id'],baseline={})
                    execute_pending(con,aid,day,float(ft['costs']['trading_cost_bps']),ft['benchmark_version'],case['participant_id'])
                assert valuate(con,aid,day,versions,float(ft['initial_capital_krw']))['status']!='NAV_INCOMPLETE'
        con.commit()
    finally: con.close()
    print('TEST_FIXTURE valuations appended; operating databases are never opened.')

if __name__=='__main__': main()
