"""Opt-in integration tests against a disposable, explicitly local PostgreSQL.

PRICE_TEST_DATABASE_URL must target database cloud_price_test on loopback.
Never use production database environment variables as a test target.
"""
from contextlib import contextmanager
import json
import os
from urllib.parse import urlparse

import pytest

from src.forward import run_prices as cli
from tests.forward.test_price_only import bars, run

URL = os.environ.get("PRICE_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="requires disposable local PRICE_TEST_DATABASE_URL")

PRESERVED = ("portfolio_decisions", "orders", "trades", "holdings_daily", "nav_daily",
             "participants", "accounts", "scheduled_jobs", "events", "system_state", "themes")


@pytest.fixture
def pg(monkeypatch):
    import psycopg
    parsed = urlparse(URL)
    assert parsed.hostname in ("127.0.0.1", "localhost") and parsed.path == "/cloud_price_test"
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute("DROP SCHEMA public CASCADE")
        admin.execute("CREATE SCHEMA public")
        admin.execute("CREATE TABLE prices_daily(asset_id TEXT,date DATE,price DOUBLE PRECISION CHECK(price>0),"
                      "source TEXT,PRIMARY KEY(asset_id,date))")
        admin.execute("INSERT INTO prices_daily VALUES ('korea_equity','2026-10-02',99,'legacy')")
        admin.execute("CREATE TABLE portfolio_decisions(effective_date DATE)")
        admin.execute("INSERT INTO portfolio_decisions VALUES ('2026-10-05')")
        admin.execute("CREATE TABLE themes(theme_id TEXT,ticker TEXT,active BOOLEAN)")
        admin.execute("INSERT INTO themes VALUES ('AI','AI',TRUE)")
        admin.execute("CREATE TABLE alembic_version(version_num TEXT)")
        admin.execute("INSERT INTO alembic_version VALUES ('0008')")
        for table in PRESERVED:
            if table in ("portfolio_decisions", "themes"):
                continue
            admin.execute(f"CREATE TABLE {table}(id TEXT,payload TEXT)")
            admin.execute(f"INSERT INTO {table} VALUES ('keep','immutable-original')")
    monkeypatch.setenv("DATABASE_BACKEND", "postgres")
    monkeypatch.setenv("CAPSTONE_DESIGN_DATABASE_URL", URL)
    monkeypatch.setenv("DATABASE_URL", "postgresql://forbidden/auth")
    yield
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute("DROP SCHEMA public CASCADE")
        admin.execute("CREATE SCHEMA public")


def snapshot():
    import psycopg
    with psycopg.connect(URL) as connection:
        return {table: connection.execute(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY 1").fetchall()
                for table in (*PRESERVED,"prices_daily")}


def test_postgres_readonly_enforced_before_any_query_and_real_cli_zero_write(pg, monkeypatch, capsys):
    import psycopg
    before = snapshot()
    with cli.operating_store(read_only=True) as store:
        assert store.connection.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"] == "on"
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            store.connection.execute("INSERT INTO events VALUES ('bad','forbidden')")
        store.connection.rollback()
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            store.connection.execute("CREATE TABLE forbidden(id TEXT)")
        store.connection.rollback()
    monkeypatch.setattr(cli,"load_frozen_benchmark",lambda p: ({}, {"tickers":{"korea_equity":"KR","FX_USDKRW":"KRW=X"}}))
    monkeypatch.setattr(cli,"collect",lambda *a,**k: pytest.fail("read-only must not fetch or write"))
    assert cli.main(["--start","2026-10-05","--dry-run", "--expected-database", "cloud_price_test",
                     "--expected-revision", "0008"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["read_only"] and report["new_points"] == 0
    assert report["target"]["database"] == "cloud_price_test"
    assert report["target"]["schema_revisions"] == ["0008"]
    assert len(report["target"]["fingerprint"]) == 16
    assert snapshot() == before


def test_postgres_wrong_target_refused_before_price_collection(pg, monkeypatch, capsys):
    before = snapshot()
    monkeypatch.setattr(cli,"load_frozen_benchmark",lambda p: ({}, {"tickers":{"korea_equity":"KR","FX_USDKRW":"KRW=X"}}))
    monkeypatch.setattr(cli,"collect",lambda *a,**k: pytest.fail("wrong target must not collect"))
    assert cli.main(["--start","2026-10-05","--expected-database","wrong_database"]) == 1
    assert cli.main(["--start","2026-10-05","--expected-revision","wrong_revision"]) == 1
    capsys.readouterr()
    assert snapshot() == before


def test_postgres_prices_only_preserves_every_other_table_retry_and_legacy(pg):
    from src.data.provider import NoPriceData
    before = snapshot()
    with cli.operating_store() as store:
        report = run(store,{"KR":bars([100],["2026-10-05"]), "KRW=X":NoPriceData("holiday")})
        assert report["new_points"] == 1
    after = snapshot()
    assert all(after[table] == before[table] for table in PRESERVED)
    assert len(after["prices_daily"]) == len(before["prices_daily"]) + 1
    assert set(before["prices_daily"]) <= set(after["prices_daily"])
    with cli.operating_store() as store:
        report = run(store,{"KR":bars([999],["2026-10-05"]), "KRW=X":NoPriceData("holiday")})
        assert report["new_points"] == 0
        assert store.existing("2026-10-05")[("korea_equity","2026-10-05")][0] == 100
    assert snapshot() == after


def test_postgres_failed_batch_rolls_back_all_prices_and_releases_lock(pg):
    import psycopg
    before = snapshot()
    with pytest.raises(psycopg.errors.CheckViolation):
        with cli.operating_store() as store:
            store.append([("korea_equity","2026-10-05",100,"test"),
                          ("korea_equity","2026-10-06",-1,"invalid")])
    assert snapshot() == before
    with cli.operating_store() as store:
        assert store.append([("korea_equity","2026-10-05",100,"test")]) == 1


def test_postgres_concurrent_price_writer_fails_loudly_and_preflight_can_read(pg):
    with cli.operating_store() as writer:
        with pytest.raises(RuntimeError, match="Another price collector"):
            with cli.operating_store(): pass
        with cli.operating_store(read_only=True) as reader:
            assert reader.coverage()[0]["last"] == "2026-10-02"


def test_postgres_partial_fetch_failure_exits_one_preserving_valid_prices(pg, monkeypatch, capsys):
    from src.data.provider import NoPriceData
    before = snapshot()
    monkeypatch.setattr(cli,"load_frozen_benchmark",lambda p: ({}, {"tickers":{"korea_equity":"KR","FX_USDKRW":"KRW=X"}}))
    collect = cli.collect
    def partial(store, tickers, **kwargs):
        from datetime import datetime
        from tests.forward.test_price_only import Source
        return collect(store, {"korea_equity":"KR","__FX__":"KRW=X"}, start=kwargs["start"],
                       now=datetime.fromisoformat("2026-10-06T01:17:00+00:00"),
                       source=Source({"KR":bars([100],["2026-10-05"]),"KRW=X":RuntimeError("network failed")}))
    monkeypatch.setattr(cli,"collect",partial)
    assert cli.main(["--start","2026-10-05"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "PARTIAL_FAILURE" and report["new_points"] == 1
    after = snapshot()
    assert all(after[table] == before[table] for table in PRESERVED)
    assert len(after["prices_daily"]) == len(before["prices_daily"]) + 1
