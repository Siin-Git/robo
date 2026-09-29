"""사용자가 고른 기본 포트폴리오가 리밸런싱 기준선이 되는가.

배경
----
run_weekly 는 참가자가 고른 기본 포트폴리오를 기준선으로 썼는데 run_monthly 는
항상 frozen 코어를 썼다. 그래서 월간 리밸런싱이 지나갈 때마다 모두의 위험도
선택이 초기화되고, 그 주 금요일 주간 배치가 되돌리는 왕복이 매달 생겼다.
(2026-09-29 수정)

주의: ``base_portfolio_selections`` 는 forward 의 SCHEMA 에 없다(ORM 전용).
테이블이 없으면 ``_base_for_participant`` 가 try/except 로 frozen 으로 떨어지므로,
테이블을 만들지 않으면 이 테스트는 무엇을 하든 통과한다.
"""
import json
import re
import sqlite3
from pathlib import Path

import pytest

from src.forward.db import init_db
from src.forward.run_weekly import _base_for_participant

FROZEN = {"us_equity": 0.60, "us_treasury": 0.40}
CONSERVATIVE = {"us_equity": 0.30, "us_treasury": 0.70}
AGGRESSIVE = {"us_equity": 0.90, "us_treasury": 0.10}

DDL = """
CREATE TABLE base_portfolio_selections (
  selection_id   TEXT PRIMARY KEY,
  user_id        TEXT,
  participant_id TEXT NOT NULL,
  status         TEXT NOT NULL,
  selected_at    TEXT NOT NULL,
  weights_json   TEXT NOT NULL
)
"""


@pytest.fixture()
def con():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    c.executescript(DDL)
    c.commit()
    return c


def _select(con, participant_id, weights, selected_at, status="active", sid=None):
    con.execute("INSERT INTO base_portfolio_selections (selection_id, user_id,"
                " participant_id, status, selected_at, weights_json)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (sid or f"S{selected_at[-8:].replace(':', '')}", "U1", participant_id,
                 status, selected_at, json.dumps(weights)))
    con.commit()


# --------------------------------------------------------------------------

def test_선택이_있으면_그_비중을_쓴다(con):
    _select(con, "P001", CONSERVATIVE, "2026-09-20T10:00:00+00:00")
    assert _base_for_participant(con, "P001", FROZEN) == CONSERVATIVE


def test_선택이_없으면_frozen_코어로_떨어진다(con):
    assert _base_for_participant(con, "P001", FROZEN) == FROZEN


def test_다른_참가자의_선택은_쓰지_않는다(con):
    _select(con, "P002", AGGRESSIVE, "2026-09-20T10:00:00+00:00")
    assert _base_for_participant(con, "P001", FROZEN) == FROZEN


def test_superseded_선택은_무시한다(con):
    _select(con, "P001", AGGRESSIVE, "2026-09-10T10:00:00+00:00",
            status="superseded", sid="S-OLD")
    assert _base_for_participant(con, "P001", FROZEN) == FROZEN


def test_활성_선택이_여럿이면_최신을_쓴다(con):
    _select(con, "P001", AGGRESSIVE, "2026-09-10T10:00:00+00:00", sid="S-OLD")
    _select(con, "P001", CONSERVATIVE, "2026-09-25T10:00:00+00:00", sid="S-NEW")
    assert _base_for_participant(con, "P001", FROZEN) == CONSERVATIVE


def test_바꾼_뒤에는_새_선택이_쓰인다(con):
    """실제 흐름: 예전 것을 superseded 로 돌리고 새 것을 active 로 넣는다."""
    _select(con, "P001", AGGRESSIVE, "2026-09-10T10:00:00+00:00", sid="S-OLD")
    con.execute("UPDATE base_portfolio_selections SET status='superseded'"
                " WHERE selection_id='S-OLD'")
    _select(con, "P001", CONSERVATIVE, "2026-09-25T10:00:00+00:00", sid="S-NEW")
    assert _base_for_participant(con, "P001", FROZEN) == CONSERVATIVE


def test_반환값은_frozen을_건드리지_않는다(con):
    """호출자가 받은 dict 를 수정해도 원본 frozen 이 오염되면 안 된다."""
    frozen = dict(FROZEN)
    got = _base_for_participant(con, "P001", frozen)
    got["us_equity"] = 0.99
    assert frozen == FROZEN


def test_테이블이_없어도_죽지_않는다():
    """캡스톤 밖 프로파일에는 이 테이블이 없다. frozen 으로 떨어져야 한다."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    assert _base_for_participant(c, "P001", FROZEN) == FROZEN


# --------------------------------------------------------------------------
# 두 배치가 같은 기준선을 쓰는가 (이 수정의 핵심)
# --------------------------------------------------------------------------

def _uses_base_selection(module_name: str) -> bool:
    root = Path(__file__).resolve().parents[2]
    text = (root / "src" / "forward" / f"{module_name}.py").read_text(encoding="utf-8")
    return re.search(r"_base_for_participant\s*\(", text) is not None


def test_주간과_월간이_모두_사용자_선택을_쓴다():
    """한쪽만 쓰면 월간이 위험도를 초기화하고 주간이 되돌리는 왕복이 생긴다.

    소스를 검사하는 이유: run_monthly 전체를 돌리려면 가격·공분산·계좌가 모두
    필요해 무겁고, 여기서 막고 싶은 회귀는 '한 줄이 frozen_w 로 되돌아가는 것'
    이라 호출 여부만 보면 충분하다.
    """
    assert _uses_base_selection("run_weekly"), "run_weekly 가 사용자 선택을 쓰지 않는다"
    assert _uses_base_selection("run_monthly"), \
        "run_monthly 가 frozen 코어로 되돌아갔다(매달 위험도가 초기화된다)"


def test_core_계좌는_여전히_frozen을_쓴다():
    """벤치마크 계좌까지 사용자 선택을 따라가면 비교 기준이 사라진다.

    core/shadow 는 frozen 비중을 그대로 복사해 쓴다. 이 줄이 사라지면
    벤치마크가 사용자마다 달라져 비교가 성립하지 않는다.
    """
    root = Path(__file__).resolve().parents[2]
    text = (root / "src" / "forward" / "run_monthly.py").read_text(encoding="utf-8")
    assert "w = dict(frozen_w)" in text, \
        "core/shadow 계좌가 frozen 벤치마크를 쓰지 않는다"
