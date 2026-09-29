"""sqlite3 연결처럼 보이는 PostgreSQL 연결 어댑터.

forward 엔진은 sqlite3 API 로 작성돼 있다(execute/fetchone/fetchall/commit,
`?` 자리표시자, r["col"] 접근). 이 모듈은 같은 사용법을 유지한 채 실제로는
PostgreSQL 과 통신하는 얇은 래퍼를 제공한다. 호출부 134곳은 수정하지 않는다.

맞춰 주는 것
  1. 자리표시자      ?            -> %s
  2. UPSERT          INSERT OR REPLACE -> INSERT ... ON CONFLICT DO UPDATE
  3. 시간 함수       datetime('now')   -> now()
  4. 조회 결과 타입  Decimal -> float, date/datetime -> ISO 문자열
                     (엔진이 float/str 로 계산하므로 SQLite 와 동작을 맞춘다)

쓰지 않는 것: executemany / rowcount / lastrowid (엔진이 사용하지 않음)
"""
from __future__ import annotations

import datetime as _dt
import json as _json
import re
from decimal import Decimal

# INSERT OR REPLACE 대상 테이블의 충돌 기준 컬럼(기본키).
# migrations/versions/0001_initial.py 의 정의와 일치해야 한다.
CONFLICT_KEYS = {
    "counters": ("name",),
    "themes": ("theme_id",),
    "model_versions": ("version_id",),
    "prices_daily": ("asset_id", "date"),
    "nav_daily": ("account_id", "date"),
    "holdings_daily": ("account_id", "date", "asset_id"),
}

_UPSERT_RE = re.compile(
    r"INSERT\s+OR\s+REPLACE\s+INTO\s+(?P<table>\w+)\s*\((?P<cols>[^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)


def qmark_to_pyformat(sql: str) -> str:
    """`?` 를 `%s` 로 바꾼다. 문자열 리터럴 안의 `?` 와 `%` 는 건드리지 않는다."""
    out, in_str, i = [], False, 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'":
            # '' 는 이스케이프된 작은따옴표
            if in_str and i + 1 < len(sql) and sql[i + 1] == "'":
                out.append("''")
                i += 2
                continue
            in_str = not in_str
            out.append(ch)
        elif in_str:
            out.append(ch)
        elif ch == "?":
            out.append("%s")
        elif ch == "%":
            out.append("%%")  # 리터럴 % 는 이스케이프
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def rewrite_upsert(sql: str) -> str:
    """INSERT OR REPLACE -> INSERT ... ON CONFLICT (pk) DO UPDATE SET ..."""
    m = _UPSERT_RE.search(sql)
    if not m:
        return sql
    table = m.group("table").lower()
    cols = [c.strip().strip('"') for c in m.group("cols").split(",") if c.strip()]
    keys = CONFLICT_KEYS.get(table)
    if not keys:
        raise ValueError(
            f"INSERT OR REPLACE 대상 테이블 '{table}' 의 충돌 기준 컬럼을 모른다. "
            f"pg_adapter.CONFLICT_KEYS 에 추가할 것.")
    updates = [c for c in cols if c not in keys]
    head = sql[:m.start()] + f"INSERT INTO {table} ({', '.join(cols)})" + sql[m.end():]
    if not updates:
        return head + f" ON CONFLICT ({', '.join(keys)}) DO NOTHING"
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in updates)
    return head + f" ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {sets}"


def translate(sql: str) -> str:
    """SQLite 용 SQL 문자열을 PostgreSQL 용으로 변환한다."""
    sql = rewrite_upsert(sql)
    sql = re.sub(r"datetime\(\s*'now'\s*\)", "now()", sql, flags=re.IGNORECASE)
    return qmark_to_pyformat(sql)


def _py(value):
    """PostgreSQL 반환값을 SQLite 와 같은 파이썬 타입으로 맞춘다."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, _dt.datetime):
        return value.isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        # JSONB 는 psycopg 가 dict/list 로 풀어서 준다. SQLite 는 TEXT 로 저장하고
        # 호출부가 json.loads() 를 하므로, 같은 계약을 유지하려면 문자열로 되돌린다.
        return _json.dumps(value, ensure_ascii=False)
    return value


class Row:
    """sqlite3.Row 흉내: r["col"], r[0], dict(r), "col" in r 를 지원."""

    __slots__ = ("_d",)

    def __init__(self, mapping: dict):
        self._d = {k: _py(v) for k, v in mapping.items()}

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._d.values())[key]
        return self._d[key]

    def keys(self):
        return list(self._d.keys())

    def values(self):
        return list(self._d.values())

    def items(self):
        return self._d.items()

    def __iter__(self):
        return iter(self._d.values())

    def __contains__(self, key):
        return key in self._d

    def __len__(self):
        return len(self._d)

    def __repr__(self):
        return f"Row({self._d!r})"


class Cursor:
    """execute 결과. 직접 순회하거나 fetchone/fetchall 로 읽는다."""

    def __init__(self, rows: list[Row], rowcount: int = -1):
        self._rows = rows
        self._i = 0
        # sqlite3 와 같은 의미: INSERT/UPDATE/DELETE 가 영향을 준 행 수.
        # SELECT 는 -1 (sqlite3 도 동일).
        self.rowcount = rowcount

    def fetchone(self):
        if self._i >= len(self._rows):
            return None
        row = self._rows[self._i]
        self._i += 1
        return row

    def fetchall(self):
        rows = self._rows[self._i:]
        self._i = len(self._rows)
        return rows

    def __iter__(self):
        return iter(self.fetchall())

    def __len__(self):
        return len(self._rows)


class PgConnection:
    """sqlite3.Connection 과 같은 방식으로 쓰는 PostgreSQL 연결."""

    def __init__(self, dsn: str):
        import psycopg
        from psycopg.rows import dict_row
        self._con = psycopg.connect(dsn, row_factory=dict_row)
        self.row_factory = None  # 호출부가 대입해도 무시 (항상 Row 반환)

    def execute(self, sql: str, params: tuple | list = ()) -> Cursor:
        cur = self._con.cursor()
        cur.execute(translate(sql), tuple(params))
        rows = []
        rowcount = -1
        if cur.description is not None:
            rows = [Row(r) for r in cur.fetchall()]
        else:
            rowcount = cur.rowcount        # INSERT/UPDATE/DELETE 영향 행 수
        cur.close()
        return Cursor(rows, rowcount)

    def executescript(self, script: str) -> None:
        raise RuntimeError(
            "PostgreSQL 백엔드에서는 스키마를 executescript 로 만들지 않는다. "
            "`alembic upgrade head` 를 사용할 것.")

    def commit(self):
        self._con.commit()

    def rollback(self):
        self._con.rollback()

    def close(self):
        self._con.close()


def to_psycopg_dsn(url: str) -> str:
    """SQLAlchemy URL(postgresql+psycopg://...) 을 psycopg 용 DSN 으로 바꾼다."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def connect_postgres(url: str) -> PgConnection:
    return PgConnection(to_psycopg_dsn(url))
