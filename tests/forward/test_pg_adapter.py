"""pg_adapter 의 SQL 변환 테스트. DB 연결 없이 돌아간다."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from src.forward.pg_adapter import Row, qmark_to_pyformat, rewrite_upsert, translate


def test_qmark_변환():
    assert qmark_to_pyformat("SELECT * FROM t WHERE a = ? AND b = ?") == \
        "SELECT * FROM t WHERE a = %s AND b = %s"


def test_문자열_안의_물음표는_그대로():
    sql = "SELECT * FROM t WHERE note = 'why?' AND a = ?"
    assert qmark_to_pyformat(sql) == "SELECT * FROM t WHERE note = 'why?' AND a = %s"


def test_퍼센트는_이스케이프():
    assert qmark_to_pyformat("SELECT 50 % 7") == "SELECT 50 %% 7"


def test_upsert_단일키():
    out = rewrite_upsert(
        "INSERT OR REPLACE INTO counters (name, value) VALUES (?, ?)")
    assert out.startswith("INSERT INTO counters (name, value)")
    assert "ON CONFLICT (name) DO UPDATE SET value = EXCLUDED.value" in out


def test_upsert_복합키():
    out = rewrite_upsert(
        "INSERT OR REPLACE INTO nav_daily (account_id, date, nav, cash_balance)"
        " VALUES (?, ?, ?, ?)")
    assert "ON CONFLICT (account_id, date) DO UPDATE SET" in out
    assert "nav = EXCLUDED.nav" in out
    assert "cash_balance = EXCLUDED.cash_balance" in out
    # 키 컬럼은 UPDATE 대상에서 빠져야 한다
    assert "account_id = EXCLUDED.account_id" not in out


def test_upsert_모르는_테이블은_에러():
    with pytest.raises(ValueError):
        rewrite_upsert("INSERT OR REPLACE INTO unknown_table (a) VALUES (?)")


def test_datetime_now_변환():
    out = translate("INSERT OR REPLACE INTO model_versions (version_id, created_at)"
                    " VALUES (?, datetime('now'))")
    assert "now()" in out
    assert "datetime(" not in out


def test_translate_전체():
    out = translate("INSERT OR REPLACE INTO prices_daily (asset_id, date, price, source)"
                    " VALUES (?, ?, ?, ?)")
    assert out == ("INSERT INTO prices_daily (asset_id, date, price, source)"
                   " VALUES (%s, %s, %s, %s)"
                   " ON CONFLICT (asset_id, date) DO UPDATE SET"
                   " price = EXCLUDED.price, source = EXCLUDED.source")


def test_일반_select은_그대로():
    assert translate("SELECT MAX(date) m FROM prices_daily") == \
        "SELECT MAX(date) m FROM prices_daily"


def test_Row_타입변환():
    r = Row({"nav": Decimal("99950074.96251874"), "date": dt.date(2026, 9, 11),
             "status": "OK", "flag": None})
    assert isinstance(r["nav"], float)
    assert r["nav"] == pytest.approx(99950074.96251874)
    assert r["date"] == "2026-09-11"          # 엔진이 문자열 날짜를 기대한다
    assert r["status"] == "OK"
    assert r["flag"] is None


def test_Row_접근방식():
    r = Row({"a": 1, "b": 2})
    assert r["a"] == 1
    assert r[0] == 1                # 인덱스 접근
    assert dict(r) == {"a": 1, "b": 2}
    assert "b" in r
    assert list(r) == [1, 2]


def test_Cursor_rowcount():
    from src.forward.pg_adapter import Cursor
    assert Cursor([], 5).rowcount == 5          # INSERT/UPDATE/DELETE
    assert Cursor([Row({"a": 1})]).rowcount == -1   # SELECT 는 -1 (sqlite3 와 동일)


def test_Row_JSONB는_문자열로():
    import json
    # psycopg 는 JSONB 를 dict 로 준다. 호출부는 json.loads() 를 하므로
    # SQLite(TEXT) 와 같게 문자열로 돌려줘야 한다.
    r = Row({"weights_json": {"us_equity": 0.266, "cash": 0.0}})
    assert isinstance(r["weights_json"], str)
    assert json.loads(r["weights_json"])["us_equity"] == 0.266


def test_Row_JSON배열도_문자열로():
    import json
    r = Row({"payload_json": [1, 2, 3]})
    assert json.loads(r["payload_json"]) == [1, 2, 3]
