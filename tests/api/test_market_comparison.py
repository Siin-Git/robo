"""Market replay, independent identities, reconfiguration and untouched ledgers."""
from itertools import combinations
import json
import math

import pytest
from sqlalchemy import select

from src.api.services import enrollment_service, market_comparison
from src.api.services import _common as C
from src.api.errors import ApiError
from src.db.models.user import User
from src.db.models.nav import NavDaily
from src.db.models.portfolio import PortfolioTarget
from src.db.models.demo_cohort import DemoSlot
from src.local.seed_capstone import seed
from src.local.demo_cohort import prepare
from src.local.capstone import EMAILS, PASSWORD


@pytest.fixture
def market(env, monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("CAPSTONE_MARKET_COMPARISON", "1")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with env.factory() as s:
        seed(s)
        invitation = prepare(s, "market-test", ["fresh@example.com"])["invitations"][0]
        s.commit()
    return env, invitation


def login(c, email=EMAILS[0], password=PASSWORD):
    r = c.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": c.cookies["ra_csrf"]}


def test_all_46_combinations_have_risk_and_actual_price_replay(market):
    env, _ = market
    themes = [a[6:] for a in market_comparison.bundle()[0].columns if a.startswith("theme:")]
    count = 0
    with env.factory() as s:
        for n in range(3):
            for ids in combinations(themes, n):
                p = enrollment_service.preview(s, {"core_id": "CORE_V0.3", "theme_ids": list(ids)})
                assert p["performance_status"] == "MARKET_PRICE_REPLAY"
                assert p["scenario_id"] is None
                risk = p["risk_comparison"]
                assert math.isfinite(risk["personalized_volatility"])
                assert risk["personalized_volatility"] <= risk["base_volatility"] + risk["max_increase_pp"] / 100 + 1e-9
                weights = {('theme:' + w['asset_id'] if w['asset_type'] == 'theme' else w['asset_id']): w['weight'] for w in p['allocation']}
                actual = market_comparison.evaluate(weights)
                levels = market_comparison.bundle()[0].loc["2026-04-01":"2026-09-11"]
                expected = sum(w * (levels[a].iloc[-1] / levels[a].iloc[0]) for a, w in weights.items() if a != "cash") + weights.get("cash", 0)
                assert actual.nav.iloc[-1] == pytest.approx(100 * expected)
                assert actual.nav.iloc[0] == pytest.approx(100)
                assert len(actual) >= 31
                count += 1
    assert count == 46


def test_signup_reconfigure_refresh_and_preserve_other_users(market):
    env, invitation = market
    c = env.client
    login(c)
    before = c.get("/api/v1/comparison/analytics").json()["reports"]
    with env.factory() as s:
        ledger_before = [(r.account_id, r.date, float(r.nav)) for r in s.scalars(select(NavDaily))]
        legacy_targets = [(r.target_id, dict(r.weights_json)) for r in s.scalars(select(PortfolioTarget))]
    r = c.post("/api/v1/auth/register", json={**invitation, "password": PASSWORD, "display_name": "새 참가자"})
    assert r.status_code == 201, r.text
    pid = r.json()["participant_id"]
    headers = login(c, invitation["email"])
    cfg = {"core_id": "CORE_V0.3", "theme_ids": ["ai", "biotech"], "reason": "인공지능과 바이오", "current_step": "review"}
    assert c.post("/api/v1/me/experiment/complete", json=cfg, headers=headers).status_code == 200
    first = c.get("/api/v1/me/comparison").json()
    assert first["data_source"] == "MARKET_PRICE_REPLAY" and first["metrics"] is not None
    ranking = c.get("/api/v1/comparison/rankings").json()
    assert ranking["total"] == ranking["registered"] == 13 and ranking["reserved"] == 0
    assert any(x["participant_id"] == pid for x in ranking["items"])
    draft = c.get("/api/v1/me/onboarding/draft").json()
    assert draft["theme_ids"] == ["ai", "biotech"]
    assert draft["reason"] == cfg["reason"]
    frontier = c.get("/api/v1/me/frontier").json()
    new = {"frontier_id": frontier["min_variance_frontier_id"], "theme_ids": ["cloud_data_center", "biotech"], "reason": "새로운 선택"}
    # CSRF remains enforced; the preview never commits a new comparison.
    assert c.post("/api/v1/me/onboarding/complete", json=new).status_code == 403
    preview = c.post("/api/v1/me/onboarding/preview", json=new).json()
    assert preview["risk_comparison"]["personalized_volatility"] is not None
    assert c.get("/api/v1/me/comparison").json() == first
    assert c.post("/api/v1/me/onboarding/complete", json={**new, "reason": " "}, headers=headers).status_code == 422
    assert c.post("/api/v1/me/onboarding/complete", json=new, headers=headers).status_code == 200
    second = c.get("/api/v1/me/comparison").json()
    assert set(second["themes"]) == set(new["theme_ids"])
    assert second["reason"] == new["reason"] and second["metrics"] != first["metrics"]
    assert second == c.get(f"/api/v1/participants/{pid}/comparison").json()
    assert len(c.get("/api/v1/me/views/current").json()["items"]) == 2
    # Autosaved editing does not change the saved comparison or its reason.
    assert c.put("/api/v1/me/onboarding/draft", json={**new, "reason": "아직 저장하지 않은 구성", "current_step": "themes"}, headers=headers).status_code == 200
    assert c.get("/api/v1/me/comparison").json() == second
    latest = {**new, "theme_ids": ["ai"], "reason": "단일 테마 재구성"}
    assert c.post("/api/v1/me/onboarding/complete", json=latest, headers=headers).status_code == 200
    assert [v["theme_id"] for v in c.get("/api/v1/me/views/current").json()["items"]] == ["ai"]
    assert c.post("/api/v1/me/onboarding/complete", json=latest, headers=headers).json()["already_completed"]
    third = c.get("/api/v1/me/comparison").json()
    login(c, invitation["email"])
    env.factory.kw["bind"].dispose()
    assert c.get("/api/v1/me/comparison").json() == third
    all_reports = c.get("/api/v1/comparison/analytics").json()["reports"]
    assert all_reports[:12] == before
    assert all(x["core_allocation"] == third["core_allocation"] for x in all_reports)
    assert c.get("/api/v1/participants/P001").status_code == 403
    with env.factory() as s:
        assert [(r.account_id, r.date, float(r.nav)) for r in s.scalars(select(NavDaily))] == ledger_before
        targets = {r.target_id: dict(r.weights_json) for r in s.scalars(select(PortfolioTarget))}
        assert all(targets[k] == v for k, v in legacy_targets)
        assert s.get(DemoSlot, "market-test:1").configuration_json["theme_ids"] == cfg["theme_ids"]


def test_missing_prices_fail_without_fabricated_performance(monkeypatch):
    levels, meta = market_comparison.bundle()
    monkeypatch.setattr(market_comparison, "bundle", lambda: (levels.drop(columns=["theme:ai"]), meta))
    with pytest.raises(ApiError, match="가격"):
        market_comparison.evaluate({"theme:ai": 1})


def test_cash_and_invalid_weights():
    cash = market_comparison.evaluate({"cash": 1})
    assert (cash.nav == 100).all()
    for weights in ({"cash": .5}, {"cash": float("nan")}, {"cash": 2, "us_equity": -1}):
        with pytest.raises(ApiError):
            market_comparison.evaluate(weights)


def test_reset_keeps_identity_and_slot_then_recreates_without_old_design(market):
    env, invitation = market
    c = env.client
    headers = login(c)
    baseline = c.get('/api/v1/comparison/analytics').json()['reports']
    assert c.post('/api/v1/me/experiment/reset', json={'confirm': True}, headers=headers).status_code == 403
    r = c.post('/api/v1/auth/register', json={**invitation, 'password': PASSWORD, 'display_name': '초기화 검증'})
    identity = r.json()
    assert r.status_code == 201
    headers = login(c, invitation['email'])
    first = {'core_id': 'CORE_V0.3', 'theme_ids': ['ai'], 'reason': '최초 구성'}
    assert c.post('/api/v1/me/experiment/complete', json=first, headers=headers).status_code == 200
    frontier = c.get('/api/v1/me/frontier').json()
    redesign = {'frontier_id': frontier['min_variance_frontier_id'], 'theme_ids': ['cloud_data_center', 'biotech'], 'reason': '이전 자유 설계'}
    assert c.post('/api/v1/me/onboarding/complete', json=redesign, headers=headers).status_code == 200
    assert c.put('/api/v1/me/onboarding/draft', json={**redesign, 'reason': '남은 초안'}, headers=headers).status_code == 200
    with env.factory() as s:
        users = [(u.user_id, u.participant_id, u.password_hash) for u in s.scalars(select(User))]
        nav = [(n.account_id, n.date, float(n.nav)) for n in s.scalars(select(NavDaily))]
        targets = [(t.target_id, dict(t.weights_json)) for t in s.scalars(select(PortfolioTarget))]
    assert c.post('/api/v1/me/experiment/reset', json={'confirm': True}).status_code == 403
    assert c.post('/api/v1/me/experiment/reset', json={'confirm': False}, headers=headers).status_code == 422
    assert c.post('/api/v1/me/experiment/reset', json={'confirm': True, 'participant_id': 'P001'}, headers=headers).status_code == 422
    r = c.post('/api/v1/me/experiment/reset', json={'confirm': True}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'setup_required'
    assert (r.json()['registered'], r.json()['reserved'], r.json()['claimed']) == (12, 1, 1)
    assert r.json()['draft']['theme_ids'] == [] and r.json()['draft']['reason'] == ''
    assert c.get('/api/v1/me/comparison').status_code == 409
    assert c.get('/api/v1/comparison/analytics').json()['reports'] == baseline
    assert c.get('/api/v1/me/onboarding/draft').json() == {'status': 'not_started'}
    assert c.get('/api/v1/me/views/current').json()['items'] == []
    assert c.post('/api/v1/me/onboarding/complete', json=redesign, headers=headers).status_code == 409
    with env.factory() as s:
        assert users == [(u.user_id, u.participant_id, u.password_hash) for u in s.scalars(select(User))]
        assert nav == [(n.account_id, n.date, float(n.nav)) for n in s.scalars(select(NavDaily))]
        assert targets == [(t.target_id, dict(t.weights_json)) for t in s.scalars(select(PortfolioTarget))]
        slot = s.get(DemoSlot, 'market-test:1')
        assert slot.user_id == identity['user_id']
        assert slot.invite_hash == __import__('hashlib').sha256(invitation['invitation_code'].encode()).hexdigest()
    # A repeated reset is safe, and the original identity can sign in again.
    assert c.post('/api/v1/me/experiment/reset', json={'confirm': True}, headers=headers).status_code == 200
    headers = login(c, invitation['email'])
    new = {**first, 'theme_ids': ['biotech'], 'reason': '초기화 후 새 구성'}
    assert c.post('/api/v1/me/experiment/complete', json=new, headers=headers).status_code == 200
    report = c.get('/api/v1/me/comparison').json()
    assert report['participant_id'] == identity['participant_id']
    assert report['themes'] == ['biotech'] and report['reason'] == new['reason']
    saved = c.get('/api/v1/me/onboarding/draft').json()
    assert saved['theme_ids'] == ['biotech'] and saved['reason'] == new['reason']
    assert c.get('/api/v1/comparison/rankings').json()['total'] == 13
    assert c.post('/api/v1/me/onboarding/complete', json=redesign, headers=headers).status_code == 200
    assert c.get('/api/v1/me/comparison').json()['reason'] == redesign['reason']
    assert c.get('/api/v1/comparison/analytics').json()['reports'][:12] == baseline
