"""Demo acceptance tests: isolated DB, real sessions, one shared metric contract."""
import numpy as np
import pytest
from sqlalchemy import select, func

from src.local.capstone import EMAILS, PASSWORD
from src.local.seed_capstone import seed
from src.db.models.user import User
from src.db.models.nav import NavDaily
from src.db.models.view import View
from src.db.models.portfolio import PortfolioTarget
from src.db.models.participant import Participant


@pytest.fixture()
def demo(env, monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    with env.factory() as s:
        seed(s)
        s.commit()
    return env


def login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return response.json()["user"]["participant_id"]


def test_seed_idempotence_and_shared_core(demo):
    with demo.factory() as s:
        models = [User, Participant, NavDaily, View, PortfolioTarget]
        before = [s.scalar(select(func.count()).select_from(m)) for m in models]
        seed(s)
        s.commit()
        assert before == [s.scalar(select(func.count()).select_from(m)) for m in models]
        assert before[0:2] == [13, 13]
        assert before[3] == 26
    c = demo.client
    reports = []
    for email in EMAILS:
        pid = login(c, email)
        own = c.get("/api/v1/me/comparison").json()
        detail = c.get(f"/api/v1/participants/{pid}/comparison").json()
        assert own == detail
        reports.append(own)
    assert len({r["start"] for r in reports}) == len({r["end"] for r in reports}) == 1
    for r in reports:
        assert r["core_allocation"] == reports[0]["core_allocation"]
        assert [p["core_nav"] for p in r["series"]] == [p["core_nav"] for p in reports[0]["series"]]
        assert r["series"][0]["personalized_nav"] == r["series"][0]["core_nav"] == 100
        assert len(r["themes"]) <= 2
        assert sum(w["weight"] for w in r["allocation"]) == pytest.approx(1)
        assert sorted(w["asset_id"] for w in r["allocation"] if w["asset_type"] == "theme") == sorted(r["themes"])
        m = r["metrics"]
        nav = np.array([p["personalized_nav"] for p in r["series"]])
        returns = nav[1:] / nav[:-1] - 1
        assert m["nav"] == pytest.approx(nav[-1])
        assert m["cumulative_return"] == pytest.approx(nav[-1] / 100 - 1)
        assert m["excess_return"] == pytest.approx(m["cumulative_return"] - m["core_return"])
        assert m["mdd"] == pytest.approx(min(nav / np.maximum.accumulate(nav) - 1), abs=1e-12, rel=0)
        assert m["volatility"] == pytest.approx(np.std(returns, ddof=1)*np.sqrt(252), abs=1e-12, rel=0)
        assert m["sharpe"] == pytest.approx(np.mean(returns)/np.std(returns, ddof=1)*np.sqrt(252), abs=1e-12, rel=0)
    excess = [r["metrics"]["excess_return"] for r in reports]
    assert min(excess) < 0 < max(excess)


def test_five_rankings_match_details_and_ranks(demo):
    c = demo.client
    login(c, EMAILS[0])
    leaders = {}
    for basis, key in {"return":"cumulative_return", "excess":"excess_return", "mdd":"mdd",
                       "volatility":"volatility", "sharpe":"sharpe"}.items():
        response = c.get(f"/api/v1/comparison/rankings?basis={basis}")
        assert response.status_code == 200
        rows = response.json()["items"]
        assert len(rows) == 13
        assert [r["rank"] for r in rows] == list(range(1,14))
        values = [r["metrics"][key] for r in rows]
        assert values == sorted(values, reverse=basis != "volatility")
        leaders[basis] = rows[0]["participant_id"]
        for row in rows:
            detail = c.get(f"/api/v1/participants/{row['participant_id']}/comparison").json()
            assert row["metrics"] == detail["metrics"]
    assert leaders["return"] != leaders["sharpe"] != leaders["mdd"]
    assert c.get("/api/v1/comparison/rankings?basis=invalid").status_code == 400


def test_comparison_privacy_readonly_and_account_switch(demo, monkeypatch):
    c = demo.client
    assert c.get("/api/v1/me/comparison").status_code == 401
    assert c.get("/api/v1/participants/P001/comparison").status_code == 401
    assert c.get("/api/v1/comparison/rankings").status_code == 401
    a = login(c, EMAILS[0])
    mine = c.get("/api/v1/me/comparison").json()
    b = login(c, EMAILS[1])
    public = c.get(f"/api/v1/participants/{a}/comparison")
    assert public.status_code == 200
    assert not {"email", "password_hash", "user_id", "account_id", "sessions"}.intersection(public.json())
    assert c.get(f"/api/v1/participants/{a}").status_code == 403
    assert c.get(f"/api/v1/participants/{a}/performance").status_code == 403
    assert c.get("/api/v1/participants/unknown/comparison").status_code == 404
    csrf = {"X-CSRF-Token": c.cookies["ra_csrf"]}
    assert c.post(f"/api/v1/participants/{b}/views", json={"theme_ids":["ai"],"reason":"demo"}, headers=csrf).status_code == 409
    assert c.post("/api/v1/auth/register",json={"email":"new@example.com","password":PASSWORD,"display_name":"new"}).status_code == 403
    assert c.post("/api/v1/auth/logout", headers=csrf).status_code == 200
    assert c.get("/api/v1/me/comparison").status_code == 401
    login(c, EMAILS[2])
    other = c.get("/api/v1/me/comparison").json()
    assert other["participant_id"] not in [a,b]
    assert other["metrics"] != mine["metrics"]
    assert c.get("/api/v1/me/comparison").json() == other
    monkeypatch.delenv("CAPSTONE_DEMO")
    assert c.get(f"/api/v1/participants/{a}/comparison").status_code == 404


def test_editable_design_is_isolated_from_comparison_and_other_users(demo):
    from src.api.design_workspace import _factory
    from src.db.models.session import Session
    c = demo.client
    first = login(c, EMAILS[0])
    snapshots = {pid: c.get(f"/api/v1/participants/{pid}/comparison").json()
                 for pid in [f"P{i:03d}" for i in range(1, 14)]}
    rankings = {basis: c.get(f"/api/v1/comparison/rankings?basis={basis}").json()
                for basis in ["return", "excess", "mdd", "volatility", "sharpe"]}
    assert c.get("/api/v1/me/base-portfolio").json()["status"] == "not_selected"
    assert c.get("/api/v1/me/views/current").json()["items"] == []
    frontier = c.get("/api/v1/me/frontier").json()
    fid = frontier["min_variance_frontier_id"]
    body = {"frontier_id": fid, "theme_ids": ["ai"], "reason": "separate design"}
    assert c.post("/api/v1/me/onboarding/complete", json=body).status_code == 403
    csrf = {"X-CSRF-Token": c.cookies["ra_csrf"]}
    assert c.put("/api/v1/me/onboarding/draft", json=body, headers=csrf).status_code == 200
    assert c.post("/api/v1/me/onboarding/preview", json=body).status_code == 200
    completed = c.post("/api/v1/me/onboarding/complete", json=body, headers=csrf)
    assert completed.status_code == 200, completed.text
    assert c.get("/api/v1/me/base-portfolio").json()["frontier_id"] == fid
    assert c.get("/api/v1/me/portfolio/summary").status_code == 200
    assert c.post("/api/v1/me/views", json={"theme_ids":["ai"], "reason":"weekly"}, headers=csrf).status_code == 201
    for pid, before in snapshots.items():
        assert c.get(f"/api/v1/participants/{pid}/comparison").json() == before
    for basis, before in rankings.items():
        assert c.get(f"/api/v1/comparison/rankings?basis={basis}").json() == before
    second = login(c, EMAILS[1])
    assert second != first
    assert c.get("/api/v1/me/onboarding/draft").json()["status"] == "not_started"
    assert c.get("/api/v1/me/base-portfolio").json()["status"] == "not_selected"
    assert c.get("/api/v1/me/views/current").json()["items"] == []
    login(c, EMAILS[0])
    assert c.get("/api/v1/me/base-portfolio").json()["frontier_id"] == fid
    assert c.get("/api/v1/me/comparison").json() == snapshots[first]
    factory = _factory(str(demo.dbfile.with_name("portfolio_design.db").resolve()))
    with factory() as s:
        assert s.scalar(select(func.count()).select_from(NavDaily)) == 0
        assert s.scalar(select(func.count()).select_from(Session)) == 0
        assert all(u.status == "disabled" and u.password_hash == "!identity-reference-only"
                   for u in s.scalars(select(User)))
    csrf = {"X-CSRF-Token": c.cookies["ra_csrf"]}
    assert c.post("/api/v1/auth/logout", headers=csrf).status_code == 200
    assert c.get("/api/v1/me/portfolio/summary").status_code == 401
    assert c.get("/api/v1/me/comparison").status_code == 401
