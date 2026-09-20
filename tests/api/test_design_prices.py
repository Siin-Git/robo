"""Design risk inputs are copied without auth/performance data or source mutation."""
from datetime import date
import sqlite3
from sqlalchemy import select, func
from src.api.design_prices import load_reference_prices
from src.db.models.price import PriceDaily
from src.db.models.nav import NavDaily
from src.db.models.user import User


def test_only_market_reference_is_imported_once(env, monkeypatch, tmp_path):
    source=tmp_path/'reference.db'
    with sqlite3.connect(source) as c:
        c.execute('create table prices_daily(asset_id text,date text,price real,source text)')
        c.execute("insert into prices_daily values ('us_equity','2026-09-11',100,'snapshot+provider-bootstrap')")
        c.execute('create table users(secret text)')
        c.execute("insert into users values ('not-to-be-copied')")
        c.execute('create table nav_daily(nav real)')
        c.execute('insert into nav_daily values (999)')
    before=source.read_bytes()
    monkeypatch.setenv('DESIGN_PRICE_SOURCE',str(source))
    with env.factory() as s:
        load_reference_prices(s);s.commit()
        load_reference_prices(s);s.commit()
        assert s.scalar(select(func.count()).select_from(PriceDaily))==1
        assert s.get(PriceDaily,('us_equity',date(2026,9,11))).price==100
        assert s.scalar(select(func.count()).select_from(User))==0
        assert s.scalar(select(func.count()).select_from(NavDaily))==0
    assert before==source.read_bytes()


def test_missing_source_is_not_replaced_with_fabricated_prices(env, monkeypatch, tmp_path):
    monkeypatch.setenv('DESIGN_PRICE_SOURCE',str(tmp_path/'absent.db'))
    with env.factory() as s:
        load_reference_prices(s)
        assert s.scalar(select(func.count()).select_from(PriceDaily))==0
    assert not (tmp_path/'absent.db').exists()
