"""Phase 3B API tests, auth-aware (Phase 3C): admin for admin paths, owners otherwise."""
import pytest

from .conftest import login, make_admin, register


@pytest.fixture()
def admin_cookies(env, monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    make_admin(env.factory)
    r = login(env.client, "admin@example.com", "admin-passphrase-12345")
    assert r.status_code == 200
    return dict(r.cookies)


@pytest.fixture()
def owner(env, monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    assert register(env.client, "owner@example.com").status_code == 201
    r = login(env.client, "owner@example.com")
    assert r.status_code == 200
    me = env.client.get("/api/v1/auth/me", cookies=dict(r.cookies)).json()
    return {"cookies": dict(r.cookies), "pid": me["participant_id"],
            "csrf": r.cookies.get("ra_csrf")}


def test_health_and_request_id(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r.headers.get("X-Request-ID")


def test_ready_states(client):
    r = client.get("/ready")
    assert r.status_code in (200, 503)
    if r.status_code == 200:
        assert r.json()["benchmark"] == "CORE_V0.3"


def test_participant_lifecycle(client, admin_cookies):
    c = client
    r = c.post("/api/v1/participants", json={"display_name": "User A"},
               cookies=admin_cookies)
    assert r.status_code == 201
    pid = r.json()["participant_id"]
    # admin itself owns a participant from make_admin, so look for ours
    ids = [p["participant_id"] for p in
           c.get("/api/v1/participants", cookies=admin_cookies).json()["items"]]
    assert pid in ids
    # unauthenticated admin path is closed
    c.cookies.clear()
    assert c.get("/api/v1/participants").status_code == 401
    # admin sees unknown IDs as 404 (no enumeration concern for admins)
    assert c.get("/api/v1/participants/P999", cookies=admin_cookies).status_code == 404
    c.post(f"/api/v1/participants/{pid}/deactivate", cookies=admin_cookies)
    c.post(f"/api/v1/participants/{pid}/reactivate", cookies=admin_cookies)
    assert pid in [p["participant_id"] for p in
                   c.get("/api/v1/participants", cookies=admin_cookies).json()["items"]]


def test_participant_owner_read(client, owner, admin_cookies):
    assert client.get(f"/api/v1/participants/{owner['pid']}",
                      cookies=owner["cookies"]).status_code == 200
    # non-admins get 403 even for unknown IDs (no enumeration oracle)
    r = client.get("/api/v1/participants/P999", cookies=owner["cookies"])
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "PARTICIPANT_ACCESS_DENIED"


def test_themes(client, owner):
    items = client.get("/api/v1/themes", cookies=owner["cookies"]).json()["items"]
    assert {t["theme_id"] for t in items} == {"ai", "semiconductor", "nuclear"}
    client.cookies.clear()
    assert client.get("/api/v1/themes").status_code == 401
    opt = client.get("/api/v1/themes/optical_networking",
                     cookies=owner["cookies"]).json()
    assert opt["active"] is False
    assert client.get("/api/v1/themes/nope", cookies=owner["cookies"]).status_code == 404


def _post_views(client, cookies, csrf, pid, themes):
    return client.post(f"/api/v1/participants/{pid}/views",
                       json={"theme_ids": themes},
                       cookies=cookies, headers={"X-CSRF-Token": csrf})


def test_views_flow_and_rules(client, owner):
    ck, csrf, pid = owner["cookies"], owner["csrf"], owner["pid"]
    r = _post_views(client, ck, csrf, pid, ["ai"])
    assert r.status_code == 201
    v = r.json()["views"][0]
    assert v["status"] == "new" and v["execution_status"] == "PENDING"
    from src.forward.views import resolve_view_schedule
    sched = resolve_view_schedule(v["submitted_at"])
    assert v["cycle_date"] == sched["cycle_date"] and v["effective_at"] == sched["effective_at"]
    assert _post_views(client, ck, csrf, pid, ["semiconductor"]).status_code == 201
    cur = client.get(f"/api/v1/participants/{pid}/views/current", cookies=ck).json()
    assert cur["total"] == 2
    assert _post_views(client, ck, csrf, pid, ["ai", "ai"]).status_code == 400
    bad = _post_views(client, ck, csrf, pid, ["optical_networking"])
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "THEME_INACTIVE"
    vid = v["view_id"]
    assert client.post(f"/api/v1/participants/{pid}/views/{vid}/close",
                       cookies=ck, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get(f"/api/v1/participants/{pid}/views/current",
                      cookies=ck).json()["total"] == 1


def test_view_limit_three_themes_rejected(client, owner):
    ck, csrf, pid = owner["cookies"], owner["csrf"], owner["pid"]
    assert client.post(f"/api/v1/participants/{pid}/views",
                       json={"theme_ids": ["ai", "semiconductor", "ai"]},
                       cookies=ck, headers={"X-CSRF-Token": csrf}).status_code == 422
    assert _post_views(client, ck, csrf, pid, ["ai"]).status_code == 201
    r = _post_views(client, ck, csrf, pid, ["semiconductor", "nuclear"])
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "VIEW_LIMIT_EXCEEDED"


def test_portfolio_endpoints(client, owner):
    import json as _json
    ck = owner["cookies"]
    core = client.get("/api/v1/portfolio/core", cookies=ck).json()
    frozen = _json.load(open("outputs/frozen/CORE_V0.3/weights.json"))
    cw = {w["asset_id"]: w["weight"] for w in core["weights"] if w["asset_type"] != "theme"}
    for aid, w in frozen.items():
        assert abs(cw.get(aid, 0.0) - w) < 1e-9
    p = client.get(f"/api/v1/participants/{owner['pid']}/portfolio", cookies=ck).json()
    assert abs(sum(w["weight"] for w in p["weights"]) - 1.0) < 1e-6
    comp = client.get(f"/api/v1/participants/{owner['pid']}/portfolio/comparison",
                      cookies=ck).json()
    assert set(comp) == {"core", "personalized", "active"}
    client.cookies.clear()
    assert client.get("/api/v1/portfolio/core").status_code == 401


def test_performance_prelaunch_and_nav_fixture(client, owner):
    ck, pid = owner["cookies"], owner["pid"]
    perf = client.get(f"/api/v1/participants/{pid}/performance", cookies=ck).json()
    assert perf["status"] == "INSUFFICIENT_HISTORY"
    assert perf["metrics"]["cumulative_return"] is None


def test_dashboard_performance_prelaunch_and_validation(client, owner):
    url = "/api/v1/me/performance/dashboard"
    ck = owner["cookies"]
    result = client.get(url, cookies=ck)
    assert result.status_code == 200
    assert result.json()["status"] == "INSUFFICIENT_HISTORY"
    assert result.json()["assets"] == []
    assert result.json()["end"] is None
    assert client.get(url, params={"period":"NOPE"}, cookies=ck).status_code == 400
    client.cookies.clear()
    assert client.get(url).status_code == 401


def test_dashboard_reads_recorded_nav_and_holdings(env, client, owner):
    from datetime import date, datetime, timezone
    from sqlalchemy import select
    from src.db.models.account import Account
    from src.db.models.nav import NavDaily
    from src.db.models.holding import Holding
    from src.db.models.order import Order
    from src.db.models.price import PriceDaily
    from src.db.models.trade import Trade
    with env.factory() as session:
        for day, price in [(7, 100), (8, 110), (9, 121)]:
            session.add(PriceDaily(asset_id="us_equity", date=date(2026, 9, day),
                                   price=price, source="test-close"))
        accounts = list(session.scalars(select(Account).where(Account.participant_id == owner["pid"])))
        for account in accounts:
            if account.account_type not in ("core", "personal"):
                continue
            for day, value in [(7,100), (8,110), (9,121)]:
                d = date(2026,9,day)
                nav = value if account.account_type == "personal" else 100
                session.add(NavDaily(account_id=account.account_id,date=d,nav=nav,nav_base100=nav,
                    daily_return=.1 if day>7 and account.account_type=="personal" else 0,
                    cumulative_return=nav/100-1,cash_balance=0,stale_price_flag=False,nav_status="OK",
                    benchmark_version="test",theme_universe_version="test",risk_model_version="test",execution_rule_version="test"))
                session.add(Holding(account_id=account.account_id,date=d,asset_id="us_equity",
                    quantity=1,price=nav,market_value=nav,weight=1))
            if account.account_type == "personal":
                submitted = datetime(2026, 9, 6, 9, tzinfo=timezone.utc)
                session.add(Order(order_id="O900", account_id=account.account_id,
                    asset_id="us_equity", side="buy", target_weight=1,
                    submitted_at=submitted, effective_at=date(2026, 9, 7),
                    status="executed", created_at=submitted))
                session.add(Order(order_id="O901", account_id=account.account_id,
                    asset_id="us_equity", side="sell", target_weight=.8,
                    submitted_at=submitted, effective_at=date(2026, 9, 10),
                    status="pending", created_at=submitted))
                session.add(Trade(trade_id="T900", order_id="O900",
                    account_id=account.account_id, asset_id="us_equity",
                    execution_at=date(2026, 9, 7), execution_price=100,
                    quantity=1, gross_value=100, transaction_cost=0,
                    net_value=100))
        session.commit()
    r = client.get("/api/v1/me/performance/dashboard?period=1M", cookies=owner["cookies"])
    assert r.status_code == 200
    report = r.json()
    assert report["metrics"]["cumulative_return"] == pytest.approx(.21)
    assert report["metrics"]["benchmark_return"] == 0
    assert report["metrics"]["difference_pp"] == pytest.approx(.21)
    assert report["end"] == "2026-09-09"
    assert sum(a["contribution"] for a in report["assets"]) == pytest.approx(.21)
    assert report["quality"]["unresolved_intervals"] == 0

    contribution = client.get(
        "/api/v1/me/performance/contributions?period=1M", cookies=owner["cookies"]
    )
    assert contribution.status_code == 200
    body = contribution.json()
    assert body["cumulative_return"] == pytest.approx(.21)
    assert body["reconciliation"]["contribution_total"] == pytest.approx(.21)
    assert body["reconciliation"]["difference"] == pytest.approx(0)
    assert body["reconciliation"]["reconciled"] is True
    assert body["method"] == "linked_asset_pnl_over_opening_nav"
    us_equity = next(a for a in body["assets"] if a["asset_id"] == "us_equity")
    assert us_equity["cumulative_contribution"] == pytest.approx(.21)
    assert body["history"][-1]["contributions"]["us_equity"] == pytest.approx(.21)

    participant_path = (
        f"/api/v1/participants/{owner['pid']}/performance/contributions?period=1M"
    )
    assert client.get(participant_path, cookies=owner["cookies"]).json() == body

    ledger_url = "/api/v1/me/performance/ledger"
    ledger = client.get(ledger_url, cookies=owner["cookies"])
    assert ledger.status_code == 200
    recorded = ledger.json()
    assert recorded["contract_version"] == "ledger-read-v2"
    assert recorded["as_of"] == "2026-09-09"
    assert recorded["snapshots"][-1]["cash_balance"] == 0
    assert recorded["snapshots"][-1]["cumulative_return"] == pytest.approx(.21)
    assert recorded["snapshots"][-1]["holdings"][0]["price_status"] == "current"
    assert recorded["snapshots"][-1]["holdings"][0]["price_source"] == "test-close"
    assert recorded["order_status_summary"] == {
        "pending": 1, "executed": 1, "cancelled": 0
    }
    pending = next(order for order in recorded["orders"] if order["status"] == "pending")
    assert pending["action_required"] is True
    assert pending["alert_type"] == "sell_required"
    assert recorded["trades"][0]["order_id"] == "O900"
    assert recorded["trades"][0]["execution_price"] == 100

    # Every request opens a new DB session; identical responses prove committed
    # ledger state survives process-level session teardown and reconnection.
    assert client.get(ledger_url, cookies=owner["cookies"]).json() == recorded
    assert client.get(ledger_url, params={"start": "bad-date"},
                      cookies=owner["cookies"]).status_code == 400
    assert client.get(ledger_url, params={"start": "2026-09-10", "end": "2026-09-01"},
                      cookies=owner["cookies"]).status_code == 400


def test_error_contract_shape(client, owner, admin_cookies):
    r = client.get("/api/v1/participants/P999", cookies=owner["cookies"])
    assert r.status_code == 403
    body = r.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["request_id"] == r.headers.get("X-Request-ID")
    bad = client.post("/api/v1/participants", json={},
                      cookies=owner["cookies"])
    assert bad.status_code in (403, 422)


def test_rankings_and_benchmarks(client, owner):
    ck = owner["cookies"]
    items = client.get("/api/v1/rankings", cookies=ck).json()["items"]
    assert len(items) == 1 and items[0]["active_return"] is None
    client.cookies.clear()
    assert client.get("/api/v1/rankings").status_code == 401
    blist = client.get("/api/v1/benchmarks", cookies=ck).json()["items"]
    assert {b["benchmark_version"] for b in blist} == {"CORE_V0.3", "neutral_60_40",
                                                      "equal_weight"}
    assert client.get("/api/v1/benchmarks/performance",
                      params={"benchmark_version": "CORE_V0.3"},
                      cookies=ck).json()["items"] == []
    assert client.get("/api/v1/benchmarks/performance",
                      params={"benchmark_version": "NOPE"},
                      cookies=ck).status_code == 404
    sys = client.get("/api/v1/system/status", cookies=ck).json()
    assert sys["benchmark_version"] == "CORE_V0.3"
    assert "database" not in sys
    assert client.get("/api/v1/version").json()["api_version"] == "0.1.0"
