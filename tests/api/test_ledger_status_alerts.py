"""GET /me/ledger/status 와 GET /me/alerts 계약 테스트.

프론트가 이 응답 형식을 전제로 작업하므로, 필드가 사라지면 실패해야 한다.
"""
from datetime import date, datetime, timezone

import pytest

from .conftest import login, register

EMAIL = "ledger-user@example.com"


def _cookies(res):
    return {k: v for k, v in res.cookies.items()}


@pytest.fixture()
def auth(client, monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    assert register(client, EMAIL).status_code == 201
    res = login(client, EMAIL)
    assert res.status_code == 200, res.text
    return _cookies(res)


def _participant_id(client, cookies):
    me = client.get("/api/v1/auth/me", cookies=cookies).json()
    return me["participant_id"]


# --------------------------------------------------------------------------
# ledger/status
# --------------------------------------------------------------------------

def test_status_인증_필요(client):
    assert client.get("/api/v1/me/ledger/status").status_code == 401


def test_status_기록이_없으면_has_history_false(client, auth):
    res = client.get("/api/v1/me/ledger/status", cookies=auth)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["has_history"] is False
    assert body["observation_count"] == 0
    assert body["data_freshness"] == "NO_DATA"


def test_status_필수_필드가_모두_있다(client, auth):
    body = client.get("/api/v1/me/ledger/status", cookies=auth).json()
    for key in ("has_history", "first_valuation_date", "last_valuation_date",
                "observation_count", "last_updated_at", "latest_price_date",
                "data_freshness", "next_rebalance_date", "stale_price_days"):
        assert key in body, f"{key} 누락"


def test_status_NAV가_있으면_구간과_개수를_보고한다(client, env, auth):
    pid = _participant_id(client, auth)
    _seed_nav(env.factory, pid, ["2026-09-09", "2026-09-10", "2026-09-11"])
    body = client.get("/api/v1/me/ledger/status", cookies=auth).json()
    assert body["has_history"] is True
    assert body["observation_count"] == 3
    assert body["first_valuation_date"] == "2026-09-09"
    assert body["last_valuation_date"] == "2026-09-11"
    # 월간 리밸런싱 설정이면 다음 달 1일
    assert body["next_rebalance_date"] == "2026-10-01"


# --------------------------------------------------------------------------
# alerts
# --------------------------------------------------------------------------

def test_alerts_인증_필요(client):
    assert client.get("/api/v1/me/alerts").status_code == 401


def test_alerts_기록이_없으면_빈_목록(client, auth):
    body = client.get("/api/v1/me/alerts", cookies=auth).json()
    assert body["items"] == []
    assert body["total"] == 0


def test_alerts_로그인_이벤트는_알림이_아니다(client, auth):
    """가입·로그인으로 events 행은 생기지만 사용자 알림에는 나오면 안 된다."""
    body = client.get("/api/v1/me/alerts", cookies=auth).json()
    types = {a["type"] for a in body["items"]}
    assert "USER_LOGGED_IN" not in types
    assert "USER_REGISTERED" not in types


def test_alerts_체결_이벤트가_알림으로_나온다(client, env, auth):
    pid = _participant_id(client, auth)
    _seed_event(env.factory, pid, "TRADE_EXECUTED",
                {"trade_id": "T001", "asset": "us_equity", "quantity": 12.5})
    body = client.get("/api/v1/me/alerts", cookies=auth).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["type"] == "TRADE_EXECUTED"
    assert item["severity"] == "info"
    assert item["title"]
    assert item["detail"]["asset"] == "us_equity"
    for key in ("alert_id", "type", "date", "occurred_at", "title", "detail", "severity"):
        assert key in item, f"{key} 누락"


def test_alerts_현금부족은_warning(client, env, auth):
    pid = _participant_id(client, auth)
    _seed_event(env.factory, pid, "CASH_SCALED", {"scale": 0.97})
    item = client.get("/api/v1/me/alerts", cookies=auth).json()["items"][0]
    assert item["severity"] == "warning"


def test_alerts_페이지네이션(client, env, auth):
    pid = _participant_id(client, auth)
    for i in range(5):
        _seed_event(env.factory, pid, "ORDER_CREATED", {"n": i}, seq=i)
    body = client.get("/api/v1/me/alerts?limit=2&offset=1", cookies=auth).json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2 and body["offset"] == 1


# --------------------------------------------------------------------------
# 가격 수집 알림
# --------------------------------------------------------------------------

def test_가격_수집_실패는_경고로_알린다(client, env, auth):
    """운용 전체에 해당하는 이벤트라 participant_id 가 비어 있어도 보여야 한다."""
    _seed_system_event(env.factory, "PRICE_REFRESH_FAILED",
                       {"error": "no FX data available", "asof": "2026-09-28"})
    body = client.get("/api/v1/me/alerts", cookies=auth).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["type"] == "PRICE_REFRESH_FAILED"
    assert item["severity"] == "warning"
    assert item["detail"]["error"] == "no FX data available"


def test_정상_수집은_알림이_아니다(client, env, auth):
    """PRICE_REFRESH 는 매일 남는다. 알림으로 내보내면 매일 울린다."""
    _seed_system_event(env.factory, "PRICE_REFRESH",
                       {"asof": "2026-09-28", "new_points": 180,
                        "fetch_failed": ["korea_equity"], "stale_assets": []})
    body = client.get("/api/v1/me/alerts", cookies=auth).json()
    assert body["items"] == [], "휴장으로 인한 조회 실패까지 알리면 거짓 경보가 된다"


def test_시스템_알림은_모든_사용자에게_보인다(client, env, two_users):
    a, b = two_users
    _seed_system_event(env.factory, "PRICE_REFRESH_FAILED", {"error": "timeout"})
    for cookies in (a, b):
        body = client.get("/api/v1/me/alerts", cookies=cookies).json()
        assert [i["type"] for i in body["items"]] == ["PRICE_REFRESH_FAILED"]


# --------------------------------------------------------------------------
# 사용자별 분리 (13명 로그인 시연 전제)
# --------------------------------------------------------------------------

USER_A = "demo-a@example.com"
USER_B = "demo-b@example.com"


@pytest.fixture()
def two_users(client, monkeypatch):
    """서로 다른 두 사용자의 쿠키를 각각 반환한다."""
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    out = []
    for email in (USER_A, USER_B):
        assert register(client, email).status_code == 201
        res = login(client, email)
        assert res.status_code == 200, res.text
        out.append(_cookies(res))
    return out


def test_ledger_status가_사용자별로_독립적이다(client, env, two_users):
    a, b = two_users
    pid_a, pid_b = _participant_id(client, a), _participant_id(client, b)
    assert pid_a != pid_b
    _seed_nav(env.factory, pid_a, ["2026-09-09", "2026-09-10", "2026-09-11"])
    _seed_nav(env.factory, pid_b, ["2026-09-11"])

    sa = client.get("/api/v1/me/ledger/status", cookies=a).json()
    sb = client.get("/api/v1/me/ledger/status", cookies=b).json()
    assert sa["observation_count"] == 3
    assert sb["observation_count"] == 1
    assert sa["first_valuation_date"] == "2026-09-09"
    assert sb["first_valuation_date"] == "2026-09-11"


def test_한_사용자만_기록이_있어도_다른_사용자는_비어있다(client, env, two_users):
    a, b = two_users
    _seed_nav(env.factory, _participant_id(client, a), ["2026-09-11"])
    sb = client.get("/api/v1/me/ledger/status", cookies=b).json()
    assert sb["has_history"] is False
    assert sb["observation_count"] == 0


def test_alerts가_사용자별로_독립적이다(client, env, two_users):
    a, b = two_users
    pid_a, pid_b = _participant_id(client, a), _participant_id(client, b)
    _seed_event(env.factory, pid_a, "TRADE_EXECUTED", {"asset": "us_equity"}, seq=1)
    _seed_event(env.factory, pid_a, "ORDER_CREATED", {"asset": "us_equity"}, seq=2)
    _seed_event(env.factory, pid_b, "CASH_SCALED", {"scale": 0.9}, seq=3)

    ba = client.get("/api/v1/me/alerts", cookies=a).json()
    bb = client.get("/api/v1/me/alerts", cookies=b).json()
    assert ba["total"] == 2
    assert bb["total"] == 1
    assert {i["type"] for i in ba["items"]} == {"TRADE_EXECUTED", "ORDER_CREATED"}
    assert {i["type"] for i in bb["items"]} == {"CASH_SCALED"}
    # 남의 알림 id 가 섞이지 않는다
    assert not ({i["alert_id"] for i in ba["items"]} & {i["alert_id"] for i in bb["items"]})


def test_계좌가_사용자별로_따로_만들어진다(client, env, two_users):
    """forward 기록은 account_id 로 쌓이므로 계좌 자체가 분리되어야 한다."""
    a, b = two_users
    with env.factory() as s:
        aid_a = _account_id(s, _participant_id(client, a))
        aid_b = _account_id(s, _participant_id(client, b))
        s.commit()
    assert aid_a != aid_b


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _account_id(session, participant_id):
    from src.db.models.account import Account
    from sqlalchemy import select
    acc = session.scalars(select(Account).where(
        Account.participant_id == participant_id,
        Account.account_type == "personal")).first()
    if acc is not None:
        return acc.account_id
    acc = Account(account_id=f"A-{participant_id}-PERSONAL", participant_id=participant_id,
                  account_type="personal", shadow_name=None,
                  benchmark_version="CORE_V0.3", inception_date=date(2026, 9, 1),
                  initial_capital_krw=100000000, status="active",
                  created_at=datetime.now(timezone.utc))
    session.add(acc)
    session.flush()
    return acc.account_id


def _seed_nav(factory, participant_id, dates):
    from src.db.models.nav import NavDaily
    with factory() as s:
        aid = _account_id(s, participant_id)
        for d in dates:
            s.add(NavDaily(account_id=aid, date=date.fromisoformat(d), nav=100000000,
                           nav_base100=100, daily_return=None, cumulative_return=0,
                           cash_balance=0, stale_price_flag=False, nav_status="OK",
                           benchmark_version="CORE_V0.3", theme_universe_version="T",
                           risk_model_version="R", execution_rule_version="E"))
        s.commit()


def _seed_system_event(factory, event_type, payload, seq=90):
    """participant_id·account_id 가 없는 운용 전체 이벤트(가격 수집 등)."""
    from src.db.models.event import Event
    with factory() as s:
        s.add(Event(event_id=f"SYS{seq:05d}", event_type=event_type,
                    participant_id=None, account_id=None,
                    timestamp=datetime(2026, 9, 28, 7, seq % 60, tzinfo=timezone.utc),
                    payload_json=payload, model_version="CORE_V0.3"))
        s.commit()


def _seed_event(factory, participant_id, event_type, payload, seq=0):
    from src.db.models.event import Event
    with factory() as s:
        aid = _account_id(s, participant_id)
        # 가입·로그인이 이미 E000001.. 을 쓰므로 테스트 전용 접두사를 쓴다.
        s.add(Event(event_id=f"TST{seq:05d}", event_type=event_type,
                    participant_id=participant_id, account_id=aid,
                    timestamp=datetime(2026, 9, 11, 3, seq, tzinfo=timezone.utc),
                    payload_json=payload, model_version="CORE_V0.3"))
        s.commit()
