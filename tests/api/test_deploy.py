"""Deployment config tests: secure cookies, CORS whitelist, PG pool, headers."""
import os


def test_secure_cookie_live_vs_demo(client, env, monkeypatch):
    from .conftest import login, register
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    assert register(client, "s@example.com").status_code == 201
    monkeypatch.setenv("APP_PROFILE", "live")
    live_flags = login(client, "s@example.com").headers.get("set-cookie", "")
    assert "Secure" in live_flags
    monkeypatch.setenv("APP_PROFILE", "demo")
    demo_flags = login(client, "s@example.com").headers.get("set-cookie", "")
    assert "Secure" not in demo_flags


def test_cors_whitelist(client):
    # Default whitelist is http://localhost:3000 (module-level config).
    from fastapi.testclient import TestClient
    from src.api.main import app
    # OPTIONS preflight is handled by middleware; plain GETs carry no ACAO.
    # Direct middleware check: allowed origin echoed, random origin rejected.
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        r = c.options("/api/v1/version", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
        r2 = c.options("/api/v1/version", headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET"})
        assert "access-control-allow-origin" not in {k.lower() for k in r2.headers}


def test_postgres_pool_config_small():
    from src.db.session import pool_kwargs_for
    kw = pool_kwargs_for("postgresql+psycopg://u:p@localhost:5432/robo_advisor")
    assert kw["pool_size"] <= 5 and kw["max_overflow"] <= 2
    assert kw["pool_pre_ping"] is True and kw["pool_recycle"] <= 300
    assert pool_kwargs_for("sqlite:///x.db") == {"connect_args": {"check_same_thread": False}}
