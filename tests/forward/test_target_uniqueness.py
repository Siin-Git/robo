"""목표 비중은 계좌·효력일·종류당 하나만 존재한다.

행이 쌓이면 같은 effective_date 에 목표가 여러 개 생기고, 이를 읽는 쪽은 전부
``ORDER BY effective_date DESC ... LIMIT 1`` 이라 동점일 때 어느 목표로 체결될지
보장되지 않는다. 월간 배치를 두 번 돌리는 사이에 View 가 바뀌면 실제로 갈린다.
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest

from src.forward.accounts import record_target
from src.forward.db import init_db

VERSIONS = {"benchmark_version": "CORE_V0.3",
            "theme_universe_version": "THEME_UNIVERSE_V0.1",
            "risk_model_version": "RISK_TEST",
            "execution_rule_version": "NEXT_AVAILABLE_CLOSE_V0"}
EFF = "2026-10-01"
W1 = {"us_equity": 0.60, "cash": 0.40}
W2 = {"us_equity": 0.50, "theme:ai": 0.10, "cash": 0.40}


@pytest.fixture()
def con():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    return c


def _rec(con, weights, effective=EFF, kind="core", account="ACC1"):
    return record_target(con, account, weights, effective, kind, VERSIONS, "CORE_V0.3", "P001")


def _count(con, **where):
    sql = "SELECT COUNT(*) AS n FROM portfolio_targets"
    if where:
        sql += " WHERE " + " AND ".join(f"{k} = ?" for k in where)
    return con.execute(sql, tuple(where.values())).fetchone()["n"]


# --------------------------------------------------------------------------

def test_같은_효력일에_두_번_기록해도_행이_하나다(con):
    _rec(con, W1)
    _rec(con, W1)
    assert _count(con) == 1


def test_같은_target_id를_유지한다(con):
    first = _rec(con, W1)
    second = _rec(con, W1)
    assert first == second


def test_비중이_바뀌면_덮어쓴다(con):
    tid = _rec(con, W1)
    again = _rec(con, W2)
    assert again == tid
    assert _count(con) == 1
    stored = con.execute("SELECT weights_json FROM portfolio_targets").fetchone()["weights_json"]
    assert json.loads(stored) == W2


def test_변화가_없으면_이벤트를_남기지_않는다(con):
    _rec(con, W1)
    n1 = con.execute("SELECT COUNT(*) AS n FROM events"
                     " WHERE event_type='PORTFOLIO_GENERATED'").fetchone()["n"]
    _rec(con, W1)
    n2 = con.execute("SELECT COUNT(*) AS n FROM events"
                     " WHERE event_type='PORTFOLIO_GENERATED'").fetchone()["n"]
    assert n1 == n2 == 1


def test_비중이_바뀌면_이벤트를_남긴다(con):
    _rec(con, W1)
    _rec(con, W2)
    assert con.execute("SELECT COUNT(*) AS n FROM events"
                       " WHERE event_type='PORTFOLIO_GENERATED'").fetchone()["n"] == 2


def test_효력일이_다르면_별도_행이다(con):
    _rec(con, W1, effective="2026-10-01")
    _rec(con, W1, effective="2026-11-01")
    assert _count(con) == 2


def test_종류가_다르면_별도_행이다(con):
    """core 와 personal 목표는 같은 날에 공존한다."""
    _rec(con, W1, kind="core")
    _rec(con, W2, kind="personal")
    assert _count(con) == 2


def test_계좌가_다르면_별도_행이다(con):
    _rec(con, W1, account="ACC1")
    _rec(con, W1, account="ACC2")
    assert _count(con) == 2
    assert _count(con, account_id="ACC1") == 1


def test_카운터를_낭비하지_않는다(con):
    """재실행할 때마다 G 번호를 소비하면 번호만 계속 늘어난다."""
    _rec(con, W1)
    after_first = con.execute("SELECT value FROM counters WHERE name='G'").fetchone()["value"]
    _rec(con, W1)
    _rec(con, W2)
    after_more = con.execute("SELECT value FROM counters WHERE name='G'").fetchone()["value"]
    assert after_more == after_first


# --------------------------------------------------------------------------
# 읽기 쪽: 이미 중복이 있는 기존 DB 를 보호한다
# --------------------------------------------------------------------------

def test_목표_조회가_전부_결정적으로_정렬한다():
    """effective_date 만으로 정렬하면 동점일 때 결과가 보장되지 않는다.

    record_target 이 중복을 막지만, 이 변경 이전에 쌓인 DB 에는 이미 중복이
    있을 수 있다. 읽기 쪽도 결정적이어야 한다.
    """
    root = Path(__file__).resolve().parents[2]
    bad = []
    for folder in ("src", "scripts"):
        for f in (root / folder).rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            text = f.read_text(encoding="utf-8")
            if "portfolio_targets" not in text:
                continue
            for m in re.finditer(r"ORDER BY effective_date DESC(.{0,60}?)LIMIT 1",
                                 text, re.S):
                if "created_at" not in m.group(1):
                    bad.append(f"{f.relative_to(root)}: {m.group(0)[:70]}")
    assert not bad, "동점 정렬이 불확정인 목표 조회:\n  " + "\n  ".join(bad)
