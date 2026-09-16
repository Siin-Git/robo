"""Frontier + base selection API tests (auth-aware)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from src.api.main import app
from src.api.dependencies import get_db
from src.db.base import Base
from src.db.models.theme import Theme

@pytest.fixture()
def env(tmp_path):
    from types import SimpleNamespace
    dbfile = tmp_path / "frontier.db"
    engine = create_engine(f"sqlite:///{dbfile}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    def override():
        s = factory()
        try:
            yield s
            s.commit()
        except:
            s.rollback()
            raise
        finally:
            s.close()
    app.dependency_overrides[get_db] = override
    with factory() as s:
        s.add(Theme(theme_id="ai", display_name="AI", theme_type="theme", ticker="AIQ", market="US", currency="USD", active=True, valid_from=date(2026,1,1), valid_to=None, universe_version="THEME_UNIVERSE_V0.1", inactive_reason=None))
        s.commit()
    with TestClient(app) as c:
        yield SimpleNamespace(client=c, factory=factory)
    app.dependency_overrides.clear()

def _login(env, email="u@example.com"):
    import os
    os.environ["ALLOW_PUBLIC_REGISTRATION"] = "true"
    env.client.post("/api/v1/auth/register", json={"email": email, "password": "test-passphrase-123", "display_name": "U"})
    r = env.client.post("/api/v1/auth/login", json={"email": email, "password": "test-passphrase-123"})
    return dict(r.cookies)

def test_frontier_basic(env):
    cookies = _login(env)
    r = env.client.get("/api/v1/me/frontier", cookies=cookies)
    assert r.status_code == 200
    data = r.json()
    assert data["frontier_version"] == "CORE_FRONTIER_V0.3"
    assert 40 <= len(data["points"]) <= 100
    assert len(data["assets"]) == 9
    # weights sum
    for p in data["points"]:
        assert abs(sum(w["weight"] for w in p["weights"]) - 1.0) < 1e-6
    # volatility monotonic non-decreasing when sorted by expected_return
    vols = [p["volatility"] for p in sorted(data["points"], key=lambda x: x["expected_return"])]
    for i in range(1, len(vols)):
        assert vols[i] >= vols[i-1] - 1e-9
    # benchmark exists
    assert any(p["frontier_id"] == data["benchmark_frontier_id"] for p in data["points"])
    # also portfolio/frontier
    r2 = env.client.get("/api/v1/portfolio/frontier", cookies=cookies)
    assert r2.status_code == 200

def test_base_selection_flow(env):
    cookies = _login(env, "b@example.com")
    # initially not selected
    r = env.client.get("/api/v1/me/base-portfolio", cookies=cookies)
    assert r.json()["status"] == "not_selected"
    # get frontier to pick a point
    fid = env.client.get("/api/v1/me/frontier", cookies=cookies).json()["points"][5]["frontier_id"]
    csrf = cookies.get("ra_csrf")
    r = env.client.post("/api/v1/me/base-portfolio", json={"frontier_id": fid}, cookies=cookies, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    assert r.json()["frontier_id"] == fid
    # history preserved
    r = env.client.get("/api/v1/me/base-portfolio/history", cookies=cookies)
    assert len(r.json()["items"]) == 1
    # second selection supersedes but history keeps both
    fid2 = env.client.get("/api/v1/me/frontier", cookies=cookies).json()["points"][10]["frontier_id"]
    env.client.post("/api/v1/me/base-portfolio", json={"frontier_id": fid2}, cookies=cookies, headers={"X-CSRF-Token": csrf})
    r = env.client.get("/api/v1/me/base-portfolio/history", cookies=cookies)
    assert len(r.json()["items"]) == 2
    assert r.json()["items"][0]["frontier_id"] == fid2
    # current reflects latest
    assert env.client.get("/api/v1/me/base-portfolio", cookies=cookies).json()["frontier_id"] == fid2
    # invalid frontier
    r = env.client.post("/api/v1/me/base-portfolio", json={"frontier_id": "F999"}, cookies=cookies, headers={"X-CSRF-Token": csrf})
    assert r.status_code == 404
    # ownership: other user cannot see
    import os
    os.environ["ALLOW_PUBLIC_REGISTRATION"] = "true"
    env.client.post("/api/v1/auth/register", json={"email": "other@example.com", "password": "test-passphrase-123", "display_name": "O"})
    r2 = env.client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "test-passphrase-123"})
    other_cookies = dict(r2.cookies)
    r = env.client.get("/api/v1/me/base-portfolio", cookies=other_cookies)
    assert r.json()["status"] == "not_selected"
