"""All 13 participants select for themselves; only saved choices rank."""
import pytest
from sqlalchemy import func, select

from src.local.capstone import EMAILS
from src.local.lab_meeting import prepare
from src.api.services import enrollment_service, market_comparison
from src.db.models.demo_cohort import DemoSlot
from src.db.models.nav import NavDaily
from src.db.models.user import User


@pytest.fixture
def lab(env, monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("CAPSTONE_MARKET_COMPARISON", "1")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    passwords = {e: f"lab-test-password-{i:02d}" for i, e in enumerate(EMAILS, 1)}
    with env.factory() as s:
        assert prepare(s, "lab-test", passwords)
        s.commit()
    return env, passwords


def login(client, email, password):
    client.cookies.clear()
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["email"] == email
    return {"X-CSRF-Token": client.cookies["ra_csrf"]}


def test_thirteen_independent_logins_choices_rankings_and_reconfiguration(lab):
    env, passwords = lab
    c = env.client
    themes = [a[6:] for a in market_comparison.bundle()[0].columns if a.startswith("theme:")]
    identities = set()
    reports = {}
    for i, email in enumerate(EMAILS):
        headers = login(c, email, passwords[email])
        identity = c.get("/api/v1/auth/me").json()
        identities.add(identity["participant_id"])
        assert c.get("/api/v1/me/experiment").json()["status"] == "setup_required"
        assert c.get("/api/v1/me/onboarding/draft").json()["theme_ids"] == []
        assert c.get("/api/v1/me/comparison").status_code == 409
        ranking = c.get("/api/v1/comparison/rankings").json()
        assert (ranking["total"], ranking["reserved"], ranking["capacity"]) == (i, 13-i, 13)
        assert ranking["data_source"] == "MARKET_PRICE_REPLAY"
        frontier = c.get("/api/v1/me/frontier").json()
        choice = {"frontier_id": frontier["benchmark_frontier_id"], "theme_ids": [themes[i % len(themes)]], "current_step": "themes"}
        assert c.put("/api/v1/me/onboarding/draft", json=choice, headers=headers).status_code == 200
        headers = login(c, email, passwords[email])
        assert c.get("/api/v1/me/onboarding/draft").json()["theme_ids"] == choice["theme_ids"]
        assert c.get("/api/v1/comparison/rankings").json()["total"] == i
        assert c.post("/api/v1/me/onboarding/complete", json=choice).status_code == 403
        r = c.post("/api/v1/me/onboarding/complete", json=choice, headers=headers)
        assert r.status_code == 200, r.text
        report = c.get("/api/v1/me/comparison").json()
        assert report["themes"] == choice["theme_ids"]
        assert report["data_source"] == "MARKET_PRICE_REPLAY"
        reports[identity["participant_id"]] = report
    assert len(identities) == 13
    ranking = c.get("/api/v1/comparison/rankings").json()
    assert ranking["total"] == ranking["registered"] == 13 and ranking["reserved"] == 0
    assert {r["participant_id"] for r in ranking["items"]} == identities
    assert "email" not in str(ranking) and "password" not in str(ranking)
    before = c.get("/api/v1/comparison/analytics").json()["reports"]
    headers = login(c, EMAILS[0], passwords[EMAILS[0]])
    own = c.get("/api/v1/auth/me").json()["participant_id"]
    updated = {"frontier_id": frontier["min_variance_frontier_id"], "theme_ids": ["ai", "biotech"]}
    assert c.post("/api/v1/me/onboarding/complete", json=updated, headers=headers).status_code == 200
    assert c.get("/api/v1/me/comparison").json()["themes"] == updated["theme_ids"]
    after = c.get("/api/v1/comparison/analytics").json()["reports"]
    assert [r for r in before if r["participant_id"] != own] == [r for r in after if r["participant_id"] != own]
    assert next(r for r in after if r["participant_id"] == own)["metrics"] != reports[own]["metrics"]
    foreign = next(pid for pid in identities if pid != own)
    assert c.get(f"/api/v1/participants/{foreign}").status_code == 403
    with env.factory() as s:
        hashes = list(s.execute(select(User.user_id, User.password_hash)))
        assert not prepare(s, "lab-test")
        assert list(s.execute(select(User.user_id, User.password_hash))) == hashes
        assert s.scalar(select(func.count()).select_from(NavDaily)) == 0
        assert all(slot.confirmed_at for slot in s.scalars(select(DemoSlot)))
        s.commit()
    env.factory.kw["bind"].dispose()
    assert c.get("/api/v1/comparison/analytics").json()["reports"] == after


def test_prepare_refuses_other_cohorts_and_live_profile(lab, monkeypatch):
    env, passwords = lab
    with env.factory() as s:
        with pytest.raises(ValueError, match="another cohort"):
            prepare(s, "different-lab", passwords)
        assert enrollment_service.active(s).cohort_id == "lab-test"
        monkeypatch.setenv("APP_PROFILE", "live")
        with pytest.raises(ValueError, match="isolated"):
            prepare(s, "lab-test", passwords)


def test_prepare_does_not_reassign_existing_demo_users(env, monkeypatch):
    from src.local.seed_capstone import seed
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("CAPSTONE_MARKET_COMPARISON", "1")
    with env.factory() as s:
        seed(s)
        with pytest.raises(ValueError, match="empty database"):
            prepare(s, "lab-test", {e: f"lab-test-password-{i}" for i, e in enumerate(EMAILS)})
        assert not list(s.scalars(select(DemoSlot)))
