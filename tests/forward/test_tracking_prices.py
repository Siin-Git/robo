from datetime import datetime, timezone
import json
import sqlite3
import pandas as pd
import pytest

from src.data.closed_sessions import ClosedSessionProvider
from src.data.provider import NoPriceData
from src.forward.prices import refresh_live
from scripts.tracking_price_schedule import collect, prices_only_authorizer, target, latest_backup


def bars(values, dates, zone, period=None):
    s = pd.Series(values, index=pd.to_datetime(dates), dtype=float)
    s.attrs['session_timezone'] = zone
    if period:
        s.attrs['regular_session'] = {k:int(pd.Timestamp(v).timestamp()) for k,v in period.items()}
    return s


class Source:
    def __init__(self, data): self.data, self.requests = data, []
    def get_price_history(self, ticker, start, end):
        self.requests.append((ticker,start,end))
        if isinstance(self.data[ticker], Exception): raise self.data[ticker]
        s = self.data[ticker]
        return s.loc[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]


def db():
    c = sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row
    c.executescript('''CREATE TABLE prices_daily(asset_id TEXT,date TEXT,price REAL,source TEXT,PRIMARY KEY(asset_id,date));
      CREATE TABLE portfolio_decisions(effective_date TEXT);
      INSERT INTO portfolio_decisions VALUES ('2026-10-05');
      CREATE TABLE themes(theme_id TEXT,ticker TEXT,active BOOLEAN);
      CREATE TABLE orders(id TEXT); INSERT INTO orders VALUES ('unchanged');''')
    return c


def test_delayed_korean_open_collects_old_sessions_not_intraday():
    s=bars([100,999],['2026-10-02','2026-10-05'],'Asia/Seoul',
           {'start':'2026-10-05T00:00Z','end':'2026-10-05T06:30Z'})
    p=ClosedSessionProvider(Source({'KR':s}),datetime.fromisoformat('2026-10-05T01:10:00+00:00'))
    result=p.get_price_history('KR','2026-10-01','2026-10-05')
    assert list(result)==[100] and p.pending['KR']==1


@pytest.mark.parametrize('now,expected', [('2026-10-05T06:59Z',0),('2026-10-05T07:00Z',1)])
def test_korean_close_waits_for_thirty_minute_buffer(now,expected):
    s=bars([100],['2026-10-05'],'Asia/Seoul',{'start':'2026-10-05T00:00Z','end':'2026-10-05T06:30Z'})
    p=ClosedSessionProvider(Source({'KR':s}),pd.Timestamp(now).to_pydatetime())
    assert len(p.get_price_history('KR','2026-10-05','2026-10-05'))==expected


@pytest.mark.parametrize('day,end,now', [('2026-10-05','2026-10-05T20:00Z','2026-10-05T22:30Z'),
                                      ('2026-11-03','2026-11-03T21:00Z','2026-11-03T22:30Z')])
def test_us_closed_session_available_next_korean_morning_in_both_dst_seasons(day,end,now):
    s=bars([100],[day],'America/New_York',{'start':day+'T14:30Z','end':end})
    p=ClosedSessionProvider(Source({'VTI':s}),pd.Timestamp(now).to_pydatetime())
    assert len(p.get_price_history('VTI',day,day))==1


@pytest.mark.parametrize('now,expected', [('2026-10-05T22:30Z',0),('2026-10-06T00:30Z',1)])
def test_fx_waits_until_source_session_date_is_over(now,expected):
    s=bars([1400],['2026-10-05'],'Europe/London')
    p=ClosedSessionProvider(Source({'KRW=X':s}),pd.Timestamp(now).to_pydatetime())
    assert len(p.get_price_history('KRW=X','2026-10-05','2026-10-06'))==expected


def test_no_close_metadata_waits_instead_of_guessing_today_is_final():
    p=ClosedSessionProvider(Source({'KR':bars([100],['2026-10-05'],'Asia/Seoul')}),
                            pd.Timestamp('2026-10-05T08:00Z').to_pydatetime())
    assert p.get_price_history('KR','2026-10-05','2026-10-05').empty


def test_exact_fx_and_incremental_second_day_preserve_history_and_no_holiday_fill():
    c=db()
    source=Source({'VTI':bars([100,101],['2026-10-05','2026-10-06'],'America/New_York'),
                   'KR':bars([200],['2026-10-05'],'Asia/Seoul'),
                   'FX':bars([1400],['2026-10-05'],'Europe/London')})
    tickers={'us_equity':'VTI','korea_equity':'KR','__FX__':'FX'}
    a=refresh_live(c,tickers,provider=source,asof='2026-10-06',initial_start='2026-10-05',observed_only=True)
    assert a['new_points']==3
    assert c.execute("SELECT price FROM prices_daily WHERE asset_id='us_equity'").fetchone()[0]==140000
    assert not c.execute("SELECT 1 FROM prices_daily WHERE date='2026-10-06'").fetchone()
    source.data['FX']=bars([1400,1410],['2026-10-05','2026-10-06'],'Europe/London')
    b=refresh_live(c,tickers,provider=source,asof='2026-10-07',initial_start='2026-10-05',observed_only=True)
    assert b['new_points']==2
    assert c.execute("SELECT price FROM prices_daily WHERE asset_id='us_equity' AND date='2026-10-06'").fetchone()[0]==142410
    assert not c.execute("SELECT 1 FROM prices_daily WHERE asset_id='korea_equity' AND date='2026-10-06'").fetchone()
    original=[tuple(r) for r in c.execute('SELECT * FROM prices_daily ORDER BY asset_id,date')]
    assert refresh_live(c,tickers,provider=source,asof='2026-10-07',observed_only=True)['new_points']==0
    assert [tuple(r) for r in c.execute('SELECT * FROM prices_daily ORDER BY asset_id,date')]==original


def test_korean_observation_does_not_require_unavailable_fx():
    c=db(); s=Source({'KR':bars([100],['2026-10-05'],'Asia/Seoul'),'FX':NoPriceData('holiday')})
    r=refresh_live(c,{'korea_equity':'KR','__FX__':'FX'},provider=s,asof='2026-10-05',observed_only=True)
    assert r['new_points']==1 and r['stale']==[]


def test_holiday_empty_is_normal_but_network_failure_is_reported():
    c=db(); s=Source({'KR':NoPriceData('holiday'),'FX':RuntimeError('connection failed')})
    r=refresh_live(c,{'korea_equity':'KR','__FX__':'FX'},provider=s,asof='2026-10-05',observed_only=True)
    assert r['new_points']==0 and r['stale']==['__FX__']


def test_collector_uses_kst_now_and_decision_floor_and_cannot_write_orders(monkeypatch):
    c=db(); c.set_authorizer(prices_only_authorizer)
    source=Source({'KR':bars([99,100],['2026-10-02','2026-10-05'],'Asia/Seoul')})
    monkeypatch.setattr('scripts.tracking_price_schedule.tickers_map',lambda *a:{'korea_equity':'KR'})
    r=collect(c,datetime.fromisoformat('2026-10-05T23:30:00+00:00'),source)
    assert r['asof']=='2026-10-06' and r['first_eligible_date']=='2026-10-05' and r['new_points']==1
    assert source.requests==[('KR','2026-10-05','2026-10-06')]
    assert c.execute('SELECT id FROM orders').fetchone()[0]=='unchanged'
    with pytest.raises(sqlite3.DatabaseError): c.execute("INSERT INTO orders VALUES ('forbidden')")


def test_target_refuses_replay_and_remote_instead_of_redirecting(tmp_path):
    path=tmp_path/'replay_ledger.db'; path.touch()
    env={'DATABASE_BACKEND':'sqlite','CAPSTONE_DESIGN_DATABASE_URL':f'sqlite:///{path}'}
    (tmp_path/'environment.json').write_text(json.dumps(env))
    with pytest.raises(ValueError): target(tmp_path)
    env.update(DATABASE_BACKEND='postgres',CAPSTONE_DESIGN_DATABASE_URL='postgresql://invalid/db')
    (tmp_path/'environment.json').write_text(json.dumps(env))
    with pytest.raises(ValueError,match='remote'): target(tmp_path)


def test_existing_local_environment_uses_explicit_data_directory_without_url(tmp_path):
    path=tmp_path/'portfolio_design.db'; path.touch()
    (tmp_path/'environment.json').write_text(json.dumps({'DATABASE_BACKEND':'sqlite',
        'CAPSTONE_DESIGN_DATABASE_URL':'','CAPSTONE_DATA_DIR':str(tmp_path)}))
    assert target(tmp_path)==path.resolve()


def test_durable_backup_retains_new_observations_and_original_decisions(tmp_path):
    c=db(); c.execute("INSERT INTO prices_daily VALUES ('korea_equity','2026-10-05',100,'test')");c.commit()
    out=tmp_path/'latest-design.db'
    latest_backup(c,out)
    with sqlite3.connect(out) as restored:
        assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert restored.execute('SELECT count(*) FROM prices_daily').fetchone()[0]==1
        assert restored.execute('SELECT effective_date FROM portfolio_decisions').fetchone()[0]=='2026-10-05'
    assert out.stat().st_mode & 0o777 == 0o600
