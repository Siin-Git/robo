from datetime import datetime, timezone
import json
import sqlite3
import pandas as pd
import pytest

from src.data.closed_sessions import ClosedSessionProvider
from src.data.provider import NoPriceData


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
