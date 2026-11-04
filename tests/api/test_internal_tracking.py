"""Professor's internal-only tracking, over isolated test DBs."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, func

from .conftest import register, login, make_admin
from .test_decisions import confirm
from src.api.services import _common as C
from src.db.models import PortfolioDecision as D, PriceDaily, Event, Order, PortfolioTarget


@pytest.fixture
def identities(client, env, monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    monkeypatch.setattr(C, "now_utc", lambda: datetime(2026, 9, 1, 2, tzinfo=timezone.utc))
    assert register(client, "tracking-user@example.com").status_code == 201
    user = dict(login(client, "tracking-user@example.com").cookies)
    make_admin(env.factory)
    admin = dict(login(client, "admin@example.com", "admin-passphrase-12345").cookies)
    return (user, {"X-CSRF-Token": user["ra_csrf"]}), (admin, {"X-CSRF-Token": admin["ra_csrf"]})


def completed(client, identities):
    response = confirm(client, identities[0])
    assert response.status_code == 200, response.text
    return response.json()["decision_id"]


def get_report(client, identities, did):
    response = client.get(f"/api/v1/admin/tracking/{did}", cookies=identities[1][0])
    assert response.status_code == 200, response.text
    return response.json()


def test_snapshot_frozen_and_excluded_from_customer_api(client, env, identities, monkeypatch):
    did = completed(client, identities)
    assert completed(client, identities) == did
    report = get_report(client, identities, did)
    assert report["snapshot_status"] == "RECORDED"
    assert report["snapshot"]["frontier"]["points"]
    theme = next(a for a in report["snapshot"]["assets"] if a["asset_id"] == "theme:ai")
    assert theme["independent_theme_forecast"] is False
    from src.api.services import portfolio_service
    from src.api.services import frontier_service
    with monkeypatch.context() as changed:
        changed.setattr(portfolio_service, "_expected_return", lambda *a: 999)
        changed.setattr(frontier_service, "get_frontier", lambda: {"points": [], "frontier_version": "changed"})
        assert get_report(client, identities, did)["snapshot"] == report["snapshot"]
    def assert_public(node):
        if isinstance(node, dict):
            assert "internal_tracking" not in node
            for value in node.values():
                assert_public(value)
        elif isinstance(node, list):
            for value in node:
                assert_public(value)
    for path in ("/me/decisions", f"/me/decisions/{did}/review", "/me/portfolio/summary"):
        response = client.get("/api/v1" + path, cookies=identities[0][0])
        assert response.status_code == 200
        assert_public(response.json())
        assert "ADMIN_ONLY" not in response.text


def test_admin_authorization_csrf_and_unknown_decision(client, identities):
    did = completed(client, identities)
    body = {"asset_id": "theme:ai", "action": "REVISION_REVIEW", "reason": "検討", "request_key": "review-001"}
    for method, path in (("GET", "/tracking"), ("GET", f"/tracking/{did}"),
                         ("POST", f"/tracking/{did}/reviews")):
        extra = {"json": body} if method == "POST" else {}
        assert client.request(method, "/api/v1/admin" + path, cookies={}, **extra).status_code == 401
        assert client.request(method, "/api/v1/admin" + path, cookies=identities[0][0],
                              headers=identities[0][1], **extra).status_code == 403
    assert client.post(f"/api/v1/admin/tracking/{did}/reviews", cookies=identities[1][0], json=body).status_code == 403
    assert client.get("/api/v1/admin/tracking/missing", cookies=identities[1][0]).status_code == 404


def test_observed_prices_honest_gaps_cash_and_kst_cutoff(client, env, identities, monkeypatch):
    did = completed(client, identities)
    with env.factory() as db:
        d = db.get(D, did)
        start = C.as_date(d.effective_date)
        # Global stored trading dates establish the visible gaps, not weekdays
        # fabricated by the reader. Pre-effective/future rows are excluded.
        for offset, value in ((-1, 1000), (0, 100), (2, 110), (3, 999)):
            db.add(PriceDaily(asset_id="theme:ai", date=start+timedelta(days=offset), price=value, source="SYNTHETIC_TEST_TRACKING"))
        db.add(PriceDaily(asset_id="gold", date=start+timedelta(days=1), price=200, source="SYNTHETIC_TEST_TRACKING"))
        db.commit()
    monkeypatch.setattr(C, "now_utc", lambda: datetime.combine(start+timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc))
    out = get_report(client, identities, did)
    assert out["data_kind"] == "TEST_FIXTURE"
    asset = next(a for a in out["assets"] if a["asset_id"] == "theme:ai")
    assert asset["observations"] == 2
    assert asset["cumulative_price_return"] == pytest.approx(.1)
    assert [p["index100"] for p in asset["price_curve"]] == [100, None, pytest.approx(110)]
    assert asset["missing_price_dates"] == [(start+timedelta(days=1)).isoformat()]
    assert asset["ledger_contribution"] is None
    assert asset["comparison"]["difference"] is None
    assert all(h["status"] == "NOT_REACHED" and h["cumulative_price_return"] is None for h in asset["horizons"])
    cash = next((a for a in out["assets"] if a["asset_id"] == "cash"), None)
    if cash:
        assert cash["price_status"] == "NOT_APPLICABLE_CASH"
        assert cash["cumulative_price_return"] is None and cash["price_curve"] == []
    # At KST midnight an observation for the new date becomes available.
    monkeypatch.setattr(C, "now_utc", lambda: datetime.combine(start+timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc)+timedelta(hours=15))
    later = next(a for a in get_report(client, identities, did)["assets"] if a["asset_id"] == "theme:ai")
    assert later["observations"] == 3


def test_zero_one_legacy_and_superseding_windows(client, env, identities, monkeypatch):
    did = completed(client, identities)
    original = get_report(client, identities, did)
    assert all(a["observations"] == 0 and a["cumulative_price_return"] is None for a in original["assets"])
    with env.factory() as db:
        d = db.get(D, did)
        start = C.as_date(d.effective_date)
        db.add(PriceDaily(asset_id="theme:ai", date=start, price=100, source="test"))
        db.add(PriceDaily(asset_id="theme:ai", date=start+timedelta(days=1), price=500, source="test"))
        data = {c.name: deepcopy(getattr(d, c.name)) for c in D.__table__.columns}
        data.update(decision_id="legacy-next", version=2, previous_decision_id=did,
                    effective_date=start+timedelta(days=1), provenance_json={})
        db.add(D(**data))
        db.commit()
    # A future successor remains pending: it must not label the operating
    # decision as historical or include the successor's price observations.
    monkeypatch.setattr(C, "now_utc", lambda: datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc))
    active = get_report(client, identities, did)
    assert active["window_status"] == "ACTIVE"
    assert active["window_end_exclusive"] == (start+timedelta(days=1)).isoformat()
    assert get_report(client, identities, "legacy-next")["window_status"] == "AWAITING_EFFECTIVE_DATE"
    monkeypatch.setattr(C, "now_utc", lambda: datetime(2026, 12, 31, tzinfo=timezone.utc))
    identities[1][0].update(dict(login(client, "admin@example.com", "admin-passphrase-12345").cookies))
    out = get_report(client, identities, did)
    a = next(a for a in out["assets"] if a["asset_id"] == "theme:ai")
    assert out["window_status"] == "SUPERSEDED"
    assert a["observations"] == 1 and a["price_status"] == "ONE_OBSERVATION"
    assert a["cumulative_price_return"] is None
    assert a["horizons"][0]["status"] == "NOT_REACHED"
    legacy = get_report(client, identities, "legacy-next")
    assert legacy["snapshot"] is None
    assert all(a["initial_estimate"] is None for a in legacy["assets"])
    summary = client.get("/api/v1/me/portfolio/summary", cookies=identities[0][0]).json()
    # The user session also elapsed while the fixture clock advanced.
    if "error" in summary:
        identities[0][0].update(dict(login(client, "tracking-user@example.com").cookies))
        summary = client.get("/api/v1/me/portfolio/summary", cookies=identities[0][0]).json()
    assert summary["rebalance_frequency"] == "monthly"
    assert summary["rebalance_frequency_source"] == "LEGACY_DEFAULT"


def test_review_append_replay_does_not_trade_or_leak(client, env, identities):
    did = completed(client, identities)
    before = get_report(client, identities, did)
    with env.factory() as db:
        counts = [db.scalar(select(func.count()).select_from(model)) for model in (D, Order, PortfolioTarget)]
    body = {"asset_id": "theme:ai", "action": "REVISION_REVIEW", "reason": "독립 테마 전망 정의 필요", "request_key": "review-note-001"}
    def post(data, headers=identities[1][1]):
        return client.post(f"/api/v1/admin/tracking/{did}/reviews", cookies=identities[1][0], headers=headers, json=data)
    result = post(body)
    assert result.status_code == 200, result.text
    assert result.json()["changes_model_or_orders"] is False
    assert post(body).json() == result.json()
    assert post({**body, "reason": "changed"}).status_code == 409
    assert post({**body, "asset_id": "outside"}).status_code == 422
    assert post({**body, "reason": " "}).status_code == 422
    after = get_report(client, identities, did)
    assert after["snapshot"] == before["snapshot"]
    assert len(after["reviews"]) == 1
    assert body["reason"] not in client.get("/api/v1/me/alerts", cookies=identities[0][0]).text
    assert body["reason"] not in client.get(f"/api/v1/me/decisions/{did}/review", cookies=identities[0][0]).text
    for path in ("/me/alerts", "/me/ledger/status", "/me/performance/ledger",
                 "/me/performance/dashboard", "/me/performance/contributions", "/me/decisions",
                 "/me/portfolio/summary", "/me/performance/comparison"):
        response = client.get("/api/v1" + path, cookies=identities[0][0])
        assert response.status_code == 200, path
        assert body["reason"] not in response.text
        assert '"internal_tracking"' not in response.text
        assert '"reviewer_id"' not in response.text
    with env.factory() as db:
        assert counts == [db.scalar(select(func.count()).select_from(model)) for model in (D, Order, PortfolioTarget)]
        assert db.scalar(select(func.count()).select_from(Event).where(Event.event_type == "INTERNAL_ASSET_REVIEW")) == 1


def test_saved_curve_estimates_and_review_survive_new_sessions_without_trading(client, env, identities):
    from src.db.models import Holding, Trade, NavDaily
    from sqlalchemy import text
    from sqlalchemy.exc import DatabaseError
    did = completed(client, identities)
    before = get_report(client, identities, did)
    captured = before["snapshot"]
    assert captured["capture"] == "AT_CONFIRMATION" and captured["visibility"] == "ADMIN_ONLY"
    assert all(a["unit"] == "fraction_per_year" and a["horizon"] == "1Y" for a in captured["assets"])
    assert sum(a["expected_return"] * a["confirmed_weight"] for a in captured["assets"]) == pytest.approx(before["portfolio_expectations"]["expected_return"]["value"])
    models = (D, PortfolioTarget, Order, Trade, Holding, NavDaily)
    with env.factory() as db:
        values = [[tuple(getattr(row, c.name) for c in model.__table__.columns) for row in db.scalars(select(model))] for model in models]
        with pytest.raises(DatabaseError):
            db.execute(text("UPDATE portfolio_decisions SET provenance_json='{}' WHERE decision_id=:id"), {"id": did})
        db.rollback()
    body = {"asset_id": "theme:ai", "action": "KEEP_OBSERVING", "reason": "immutable session persistence",
            "request_key": "persistence-review-001", "reviewer_id": "forged"}
    result = client.post(f"/api/v1/admin/tracking/{did}/reviews", cookies=identities[1][0], headers=identities[1][1], json=body)
    assert result.status_code == 200
    assert result.json()["reviewer_id"] != "forged"
    # Close the reader's Session and authenticate again; persisted values remain.
    admin = dict(login(client, "admin@example.com", "admin-passphrase-12345").cookies)
    out = client.get(f"/api/v1/admin/tracking/{did}", cookies=admin).json()
    assert out["snapshot"] == captured
    assert len(out["reviews"]) == 1 and out["reviews"][0]["review_id"] == result.json()["review_id"]
    with env.factory() as db:
        assert values == [[tuple(getattr(row, c.name) for c in model.__table__.columns) for row in db.scalars(select(model))] for model in models]


def test_internal_admin_reads_design_store_without_enrolling_operator(client, env, identities, monkeypatch):
    from src.api import design_prices
    from src.api.design_workspace import _factory
    # First confirm in auth/comparison DB, then switch to a distinct design DB.
    auth_did = completed(client, identities)
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setattr(design_prices, "load_reference_prices", lambda db: None)
    design_did = completed(client, identities)
    assert design_did != auth_did
    listing = client.get("/api/v1/admin/tracking", cookies=identities[1][0]).json()
    assert [item["decision_id"] for item in listing["items"]] == [design_did]
    assert client.get(f"/api/v1/admin/tracking/{auth_did}", cookies=identities[1][0]).status_code == 404
    assert get_report(client, identities, design_did)["snapshot_status"] == "RECORDED"
    from src.db.models import User
    with _factory(f"sqlite:///{env.dbfile.with_name('portfolio_design.db')}")() as db:
        assert db.scalar(select(User).where(User.email == "admin@example.com")) is None


def test_pending_target_display_never_makes_actual_holdings_or_action(client, identities):
    did = completed(client, identities)
    d = get_report(client, identities, did)
    state = client.get("/api/v1/me/ledger/status", cookies=identities[0][0]).json()["rebalance"]
    assert state["target_context"] == "PENDING_DECISION"
    assert state["target_effective_date"] == d["window_start"]
    assert state["status"] == "NO_VALUATION"
    assert all(a["current_weight"] is None and a["action"] is None for a in state["assets"])


def test_three_six_month_observations_never_become_forecast_deltas(client, env, identities, monkeypatch):
    did = completed(client, identities)
    with env.factory() as db:
        start = C.as_date(db.get(D, did).effective_date)
        import pandas as pd
        due3 = (pd.Timestamp(start) + pd.DateOffset(months=3)).date()
        due6 = (pd.Timestamp(start) + pd.DateOffset(months=6)).date()
        for day, price in ((start, 100), (due3, 120), (due6, 130)):
            db.add(PriceDaily(asset_id="theme:ai", date=day, price=price, source="SYNTHETIC_TEST"))
        db.commit()
    for today, expected_status in ((due3, ["REACHED", "NOT_REACHED"]), (due6, ["REACHED", "REACHED"])):
        monkeypatch.setattr(C, "now_utc", lambda today=today: datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc))
        identities[1][0].update(dict(login(client, "admin@example.com", "admin-passphrase-12345").cookies))
        asset = next(a for a in get_report(client, identities, did)["assets"] if a["asset_id"] == "theme:ai")
        assert [h["status"] for h in asset["horizons"]] == expected_status
        assert asset["horizons"][0]["cumulative_price_return"] == pytest.approx(.2)
        assert asset["horizons"][1]["cumulative_price_return"] == (pytest.approx(.3) if today == due6 else None)
        assert asset["comparison"]["status"] == "NOT_COMPARABLE"
        assert asset["comparison"]["difference"] is None
