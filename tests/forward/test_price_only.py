"""Completed session collection, retry boundaries and price-only capabilities."""
from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import sqlite3

import pandas as pd
import pytest
import yaml

from src.data.provider import NoPriceData
from src.forward import run_prices as cli


def bars(values, dates, zone="Asia/Seoul", period=None):
    series = pd.Series(values, index=pd.to_datetime(dates), dtype=float)
    series.attrs["session_timezone"] = zone
    if period:
        series.attrs["regular_session"] = {key: int(pd.Timestamp(value).timestamp())
                                           for key, value in period.items()}
    return series


class Source:
    def __init__(self, data):
        self.data = data
        self.requests = []

    def get_price_history(self, ticker, start, end):
        self.requests.append((ticker, start, end))
        value = self.data[ticker]
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture
def store():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript("""
      CREATE TABLE prices_daily(asset_id TEXT, date TEXT, price REAL, source TEXT,
                                PRIMARY KEY(asset_id,date));
      CREATE TABLE portfolio_decisions(effective_date TEXT);
      INSERT INTO portfolio_decisions VALUES ('2026-10-05');
      CREATE TABLE themes(theme_id TEXT,ticker TEXT,active BOOLEAN);
      INSERT INTO themes VALUES ('AI','AI',1);
      CREATE TABLE orders(id TEXT); INSERT INTO orders VALUES ('unchanged');
    """)
    return cli.PriceStore(connection)


def run(store, data, tickers=None, now="2026-10-07T01:17:00+00:00"):
    return cli.collect(store, tickers or {"korea_equity": "KR", "__FX__": "KRW=X"},
                       start="2026-10-05", now=datetime.fromisoformat(now), source=Source(data))


def test_delayed_morning_retains_old_rows_and_rejects_live_quote(store):
    store.connection.execute("INSERT INTO prices_daily VALUES ('korea_equity','2026-10-02',99,'legacy')")
    data = {"KR": bars([111,222], ["2026-10-02","2026-10-05"], period={
        "start":"2026-10-05T00:00Z", "end":"2026-10-05T06:30Z"}),
        "KRW=X": NoPriceData("holiday")}
    report = run(store, data, now="2026-10-05T01:10:00+00:00")
    assert report["new_points"] == 0 and report["pending"]["korea_equity"] == 1
    assert store.existing("2015-01-01") == {("korea_equity","2026-10-02"): (99.0,"legacy")}
    report = run(store, data, now="2026-10-05T08:17:00+00:00")
    assert report["new_points"] == 1
    assert store.connection.execute("SELECT id FROM orders").fetchone()[0] == "unchanged"


def test_exact_fx_pending_then_same_day_retry_and_no_holiday_fill(store):
    data = {"VTI": bars([100], ["2026-10-05"], "America/New_York", period={
                "start":"2026-10-05T13:30Z", "end":"2026-10-05T20:00Z"}),
            "KR": bars([200], ["2026-10-05"]),
            "KRW=X": bars([1400], ["2026-10-05"], "Europe/London")}
    tickers = {"us_equity":"VTI", "korea_equity":"KR", "__FX__":"KRW=X"}
    early = run(store, data, tickers, "2026-10-05T22:30:00+00:00")
    assert early["new_points"] == 1 and early["missing_fx"] == {"us_equity":["2026-10-05"]}
    complete = run(store, data, tickers, "2026-10-06T00:17:00+00:00")
    assert complete["new_points"] == 2
    assert store.existing("2026-10-05")[("us_equity","2026-10-05")][0] == 140000
    before = store.existing("2026-10-05")
    assert run(store, data, tickers)["new_points"] == 0
    assert store.existing("2026-10-05") == before
    assert not any(day == "2026-10-06" for asset, day in before)


def test_late_missing_price_before_latest_is_retried_without_rewriting(store):
    store.append([("korea_equity","2026-10-06",200,"old")])
    report = run(store, {"KR":bars([100,999], ["2026-10-05","2026-10-06"]),
                         "KRW=X":NoPriceData("holiday")})
    assert report["new_points"] == 1
    assert store.existing("2026-10-05") == {
        ("korea_equity","2026-10-05"):(100,cli.SOURCE),
        ("korea_equity","2026-10-06"):(200,"old")}


def test_fx_fetch_failure_does_not_convert_with_stale_stored_fx(store):
    store.append([("__FX__","2026-10-05",999,"legacy")])
    report = run(store, {"VTI":bars([100], ["2026-10-05"],"America/New_York"),
                         "KRW=X":RuntimeError("https://credentials-must-not-appear")},
                 {"us_equity":"VTI","__FX__":"KRW=X"})
    assert report["errors"] == {"__FX__":"RuntimeError"}
    assert report["new_points"] == 0 and report["missing_fx"]
    assert "credentials" not in json.dumps(report)


def test_empty_holiday_normal_partial_failure_loud_and_independent_prices_valid(store):
    assert run(store, {"KR":NoPriceData("holiday"),"KRW=X":NoPriceData("holiday")})["errors"] == {}
    report = run(store, {"KR":bars([100],["2026-10-05"]),"KRW=X":RuntimeError("network")})
    assert report["status"] == "PARTIAL_FAILURE" and report["new_points"] == 1
    assert report["errors"] == {"__FX__":"RuntimeError"}


@pytest.mark.parametrize("value", [float("inf"),float("nan"),0,-1])
def test_invalid_provider_prices_fail_the_asset_without_poisoning_store(store, value):
    report = run(store, {"KR":bars([value],["2026-10-05"]),"KRW=X":NoPriceData("holiday")})
    assert report["errors"] == {"korea_equity":"ValueError"}
    assert not store.existing("2026-10-05")


def test_boundary_and_no_future_query(store):
    assert store.boundary("2026-09-12") == "2026-10-05"
    assert store.boundary("2026-10-07") == "2026-10-07"
    source = Source({})
    report = cli.collect(store, {"KR":"KR"}, start="2026-10-08",
                         now=datetime.fromisoformat("2026-10-07T01:00+00:00"), source=source)
    assert report["new_points"] == 0 and source.requests == []


def test_append_conflict_never_overwrites(store):
    assert store.append([("korea_equity","2026-10-05",100,"original")]) == 1
    assert store.append([("korea_equity","2026-10-05",999,"later")]) == 0
    assert store.existing("2026-10-05")[("korea_equity","2026-10-05")] == (100,"original")


def test_price_only_sql_surface_never_mutates_nonprice_tables(store):
    writes = []
    def authorize(action, table, column, database, trigger):
        if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE):
            writes.append((action,table))
            return sqlite3.SQLITE_OK if table == "prices_daily" else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    store.connection.set_authorizer(authorize)
    run(store, {"KR":bars([100],["2026-10-05"]),"KRW=X":NoPriceData("holiday")})
    assert writes == [(sqlite3.SQLITE_INSERT,"prices_daily")]


def test_read_only_plan_does_not_fetch_or_write_and_errors_exit_nonzero(store, monkeypatch, capsys):
    @contextmanager
    def fake_store(*, read_only):
        store.read_only = read_only
        yield store
    monkeypatch.setattr(cli,"operating_store",fake_store)
    monkeypatch.setattr(cli,"load_frozen_benchmark",lambda p: ({}, {"tickers":{"korea_equity":"KR","FX_USDKRW":"KRW=X"}}))
    def forbidden(*args, **kwargs):
        raise AssertionError("read-only must not enter collection")
    monkeypatch.setattr(cli,"collect",forbidden)
    assert cli.main(["--start","2026-10-05","--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["read_only"] is True and report["new_points"] == 0
    with pytest.raises(PermissionError): store.append([])
    monkeypatch.setattr(cli,"collect",lambda *a,**k: {"errors":{"__FX__":"RuntimeError"},"new_points":1})
    assert cli.main(["--start","2026-10-05"]) == 1


def test_operating_target_requires_design_postgres_and_never_falls_back(monkeypatch):
    monkeypatch.setenv("DATABASE_BACKEND","sqlite")
    with pytest.raises(ValueError):
        with cli.operating_store(): pass
    monkeypatch.setenv("DATABASE_BACKEND","postgres")
    monkeypatch.delenv("CAPSTONE_DESIGN_DATABASE_URL",raising=False)
    monkeypatch.setenv("DATABASE_URL","postgresql://must-never-use/auth")
    with pytest.raises(ValueError):
        with cli.operating_store(read_only=True): pass


def test_workflow_price_only_and_trading_requires_separate_explicit_enable():
    workflows = Path(".github/workflows")
    daily = (workflows/"daily_forward.yml").read_text()
    assert "src.forward.run_prices" in daily and "src.forward.run_daily" not in daily
    assert "--force" not in daily and "--start 2026-10-05" in daily
    assert 'cron: "30 22 * * *"' in daily and 'cron: "17 0,8 * * *"' in daily
    assert "group: forward-jobs" in daily
    assert "ref:" not in daily  # schedule uses repository default branch; dispatch uses selected ref
    for name in ("weekly_views.yml","monthly_rebalance.yml"):
        workflow = yaml.safe_load((workflows/name).read_text())
        condition = next(iter(workflow["jobs"].values()))["if"]
        assert condition == "${{ vars.FORWARD_EXECUTOR == 'actions' && vars.FORWARD_TRADING_ENABLED == 'true' }}"
        assert "||" not in condition and "inputs.dry_run" not in condition
