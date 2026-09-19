"""Shared API test fixtures: isolated SQLite DB + seeded themes per test."""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.dependencies import get_db
from src.api.main import app
from src.db.base import Base
from src.db.models.theme import Theme

THEME_SEED = [
    ("ai", "AI", "theme", "AIQ"),
    ("semiconductor", "Semi", "sector", "SOXX"),
    ("nuclear", "Nuclear", "theme", "URA"),
    ("optical_networking", None, "theme", None),
]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    # Tests must not inherit a developer's .env.local auth policy.
    monkeypatch.setenv("APP_PROFILE", "demo")
    monkeypatch.delenv("CAPSTONE_DEMO", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    dbfile = tmp_path / "api.db"
    engine = create_engine(f"sqlite:///{dbfile}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)

    def override():
        s = factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    with factory() as s:
        for tid, name, ttype, ticker in THEME_SEED:
            s.add(Theme(theme_id=tid, display_name=name or tid, theme_type=ttype,
                        ticker=ticker, market="US" if ticker else None,
                        currency="USD" if ticker else None, active=ticker is not None,
                        valid_from=date(2026, 1, 1), valid_to=None,
                        universe_version="THEME_UNIVERSE_V0.1",
                        inactive_reason=None if ticker else "no acceptable single ETF proxy"))
        s.commit()
    with TestClient(app) as c:
        yield SimpleNamespace(client=c, factory=factory, dbfile=dbfile)
    app.dependency_overrides.clear()


@pytest.fixture()
def client(env):
    return env.client


def register(client, email, password="supersecure-passphrase-123", display_name="U"):
    return client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "display_name": display_name})


def login(client, email, password="supersecure-passphrase-123"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def make_admin(factory, email="admin@example.com",
               password="admin-passphrase-12345"):
    """Create an admin directly (bypasses registration policy, tests only)."""
    from src.api.services import auth_service as auth
    with factory() as s:
        u = auth.register(s, email, password, "Admin", role="admin")
        s.commit()
        return u
