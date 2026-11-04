"""Stored FX refresh inputs must not change investment/valuation rules."""
import sqlite3
import pandas as pd
from src.forward.prices import refresh_live

def test_fx_persists_and_holiday_empty_refresh_uses_stored_input(monkeypatch):
    from src.forward.db import init_db
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row;init_db(con)
    class Provider:
        empty=False
        def get_price_history(self,ticker,start,end):
            if self.empty:raise RuntimeError('No fresh holiday close')
            return pd.Series([100.,101.],index=pd.to_datetime(['2026-10-01','2026-10-02']))
    provider=Provider();monkeypatch.setattr('src.forward.prices.get_default_provider',lambda:provider)
    report=refresh_live(con,{'us_equity':'SPY','__FX__':'KRW=X'})
    assert report['new_points']==4
    assert con.execute("SELECT COUNT(*) FROM prices_daily WHERE asset_id='__FX__'").fetchone()[0]==2
    original=con.execute('SELECT * FROM prices_daily ORDER BY asset_id,date').fetchall()
    provider.empty=True
    report=refresh_live(con,{'us_equity':'SPY','__FX__':'KRW=X'})
    assert report['new_points']==0
    assert con.execute('SELECT * FROM prices_daily ORDER BY asset_id,date').fetchall()==original



def test_fx_input_does_not_advance_nav_date(monkeypatch):
    from src.forward.db import init_db
    from src.forward.config import load_forward_config
    from src.forward.run_daily import _execute_daily
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row;init_db(con)
    con.execute("INSERT INTO prices_daily VALUES ('us_equity','2026-10-02',100,'test')")
    con.execute("INSERT INTO prices_daily VALUES ('__FX__','2026-10-05',1400,'test')")
    con.commit()
    monkeypatch.setattr('src.forward.prices.refresh_live',lambda *a:dict(new_points=0,stale=[],asof='2026-10-05'))
    code,stats=_execute_daily(con,load_forward_config(),'2026-10-05')
    assert code==0 and stats['asof']=='2026-10-02'
    assert con.execute('SELECT COUNT(*) FROM nav_daily').fetchone()[0]==0
