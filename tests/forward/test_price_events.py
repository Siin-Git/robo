"""가격 수집 결과를 events 에 남긴다 (5단계 완료 기준 · 7단계 실패 감지).

핵심 구분: "오늘 종가가 아직 없다"(휴장·마감 전)와 "가격이 실제로 밀렸다".
전자는 매일 정상적으로 일어나므로 알림으로 내보내면 거짓 경보가 된다.

실제 사례 (2026-09-28 07:50 실행):
  refresh: {'new_points': 0, 'stale': ['korea_equity', 'korea_treasury'], ...}
  -> 추석 연휴(09-24~26)로 조회 구간에 한국 거래일이 없어 예외가 났을 뿐,
     장애가 아니다. 마지막 가격은 09-23 으로 3일 전이라 밀린 것도 아니다.
"""
import sqlite3

import pytest

from src.forward.db import init_db
from src.forward.run_daily import refresh_payload, stale_assets

ASOF = "2026-09-28"


@pytest.fixture()
def con():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    return c


def _price(con, asset, date_, px=100.0):
    con.execute("INSERT OR REPLACE INTO prices_daily (asset_id, date, price, source)"
                " VALUES (?, ?, ?, 'test')", (asset, date_, px))
    con.commit()


# --------------------------------------------------------------------------
# stale_assets
# --------------------------------------------------------------------------

def test_최근_가격이_있으면_밀린_자산이_아니다(con):
    _price(con, "us_equity", "2026-09-25")
    assert stale_assets(con, ASOF, 14) == []


def test_추석_휴장_정도의_공백은_밀린_것이_아니다(con):
    """09-23 이 마지막이어도 5일 전이라 14일 기준을 넘지 않는다."""
    _price(con, "korea_equity", "2026-09-23")
    _price(con, "korea_treasury", "2026-09-23")
    assert stale_assets(con, ASOF, 14) == []


def test_기준을_넘기면_밀린_자산이다(con):
    _price(con, "us_equity", "2026-09-25")
    _price(con, "gold", "2026-09-01")          # 27일 전
    assert stale_assets(con, ASOF, 14) == ["gold"]


def test_경계값은_밀린_것으로_보지_않는다(con):
    _price(con, "us_equity", "2026-09-14")     # 정확히 14일 전
    assert stale_assets(con, ASOF, 14) == []
    _price(con, "gold", "2026-09-13")          # 15일 전
    assert stale_assets(con, ASOF, 14) == ["gold"]


def test_여러_자산이_밀리면_정렬해서_돌려준다(con):
    _price(con, "us_equity", "2026-08-01")
    _price(con, "gold", "2026-08-01")
    _price(con, "korea_equity", "2026-09-25")
    assert stale_assets(con, ASOF, 14) == ["gold", "us_equity"]


def test_가격이_없으면_빈_목록이다(con):
    assert stale_assets(con, ASOF, 14) == []


# --------------------------------------------------------------------------
# refresh_payload
# --------------------------------------------------------------------------

def test_실제_휴장_사례가_경보로_분류되지_않는다(con):
    """2026-09-28 아침 실행을 그대로 재현한다."""
    _price(con, "korea_equity", "2026-09-23")
    _price(con, "korea_treasury", "2026-09-23")
    _price(con, "us_equity", "2026-09-25")
    rep = {"new_points": 0, "stale": ["korea_equity", "korea_treasury"], "asof": ASOF}
    out = refresh_payload(con, rep, 14)
    assert out["fetch_failed"] == ["korea_equity", "korea_treasury"]
    assert out["stale_assets"] == [], "휴장을 밀린 가격으로 분류하면 거짓 경보가 된다"


def test_조회_실패와_밀림이_동시에_나올_수_있다(con):
    _price(con, "gold", "2026-08-01")
    _price(con, "us_equity", "2026-09-25")
    rep = {"new_points": 5, "stale": ["gold"], "asof": ASOF}
    out = refresh_payload(con, rep, 14)
    assert out["fetch_failed"] == ["gold"]
    assert out["stale_assets"] == ["gold"]


def test_payload_필수_필드(con):
    out = refresh_payload(con, {"new_points": 3, "stale": [], "asof": ASOF}, 14)
    for key in ("asof", "new_points", "fetch_failed", "stale_assets", "stale_price_days"):
        assert key in out, f"{key} 누락"
    assert out["new_points"] == 3
    assert out["stale_price_days"] == 14


def test_빈_보고도_처리한다(con):
    out = refresh_payload(con, {"asof": ASOF}, 14)
    assert out["new_points"] == 0
    assert out["fetch_failed"] == []


def test_asof가_없으면_밀림_판정을_생략한다(con):
    _price(con, "gold", "2026-08-01")
    out = refresh_payload(con, {"new_points": 0, "stale": []}, 14)
    assert out["stale_assets"] == []


# --------------------------------------------------------------------------
# 이벤트 기록
# --------------------------------------------------------------------------

def test_수집_결과가_events_에_남는다(con):
    """run_daily 가 refresh 결과를 반드시 기록한다.

    (2026-09-28 이전에는 print 만 하고 아무 데도 남기지 않아서, 수집이 실패해도
    GitHub Actions 로그 외에는 흔적이 없었다.)
    """
    from src.forward.db import log_event
    _price(con, "us_equity", "2026-09-25")
    rep = {"new_points": 180, "stale": ["korea_equity"], "asof": ASOF}
    log_event(con, "PRICE_REFRESH", "CORE_V0.3", payload=refresh_payload(con, rep, 14))
    con.commit()
    row = con.execute("SELECT payload_json FROM events"
                      " WHERE event_type='PRICE_REFRESH'").fetchone()
    assert row is not None
    import json
    payload = json.loads(row["payload_json"])
    assert payload["new_points"] == 180
    assert payload["fetch_failed"] == ["korea_equity"]
