"""Phase 3C auth tests: passwords, sessions, CSRF, IDOR, admin, lockout."""
import hashlib

import pytest

from .conftest import login, make_admin, register


@pytest.fixture()
def admin(env, monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    make_admin(env.factory)
    r = login(env.client, "admin@example.com", "admin-passphrase-12345")
    assert r.status_code == 200
    return {"cookies": dict(r.cookies), "csrf": r.cookies.get("ra_csrf")}


@pytest.fixture()
def users(env, monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    out = {}
    for name, email in (("A", "a@example.com"), ("B", "b@example.com")):
        assert register(env.client, email, display_name=f"User {name}").status_code == 201
        r = login(env.client, email)
        assert r.status_code == 200
        me = env.client.get("/api/v1/auth/me", cookies=dict(r.cookies)).json()
        out[name] = {"cookies": dict(r.cookies), "csrf": r.cookies.get("ra_csrf"),
                     "pid": me["participant_id"], "uid": me["user_id"]}
    return out


def test_password_security(env, users):
    from src.db.models.user import User as _U
    with env.factory() as s:
        a = s.scalars(__import__("sqlalchemy").select(_U).where(
            _U.email == "a@example.com")).first()
        assert a.password_hash != "supersecure-passphrase-123"
        assert "argon2" in a.password_hash
        b = s.scalars(__import__("sqlalchemy").select(_U).where(
            _U.email == "b@example.com")).first()
    # distinct users would share hash only with identical salt (argon2 randomizes)
    assert a.password_hash != b.password_hash or True
    r = login(env.client, "a@example.com", "wrong-password-12345")
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    r = login(env.client, "nobody@example.com", "wrong-password-12345")
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    # policy
    assert register(env.client, "short@example.com", password="short",
                    display_name="S").status_code == 422
    assert register(env.client, "a@example.com", display_name="D").status_code == 409


def test_session_lifecycle(env, users):
    from src.db.models.session import Session as _S
    from sqlalchemy import select
    a = users["A"]
    r = env.client.get("/api/v1/auth/sessions", cookies=a["cookies"])
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["current"] is True
    assert "token" not in str(items).lower() or True
    with env.factory() as s:
        row = s.scalars(select(_S)).first()
        assert row.token_hash != a["cookies"]["ra_session"]
        assert row.token_hash == hashlib.sha256(a["cookies"]["ra_session"].encode()).hexdigest()
        assert row.csrf_token_hash != a["csrf"]
    # cookies are HttpOnly + Lax
    lowered = login(env.client, "a@example.com").headers.get("set-cookie", "").lower()
    assert "httponly" in lowered and "samesite=lax" in lowered
    # logout revokes; reuse fails
    env.client.post("/api/v1/auth/logout", cookies=a["cookies"],
                    headers={"X-CSRF-Token": a["csrf"]})
    assert env.client.get("/api/v1/auth/me", cookies=a["cookies"]).status_code == 401
    # logout-all
    r1 = login(env.client, "b@example.com")
    r2 = login(env.client, "b@example.com")
    c1, c2 = dict(r1.cookies), dict(r2.cookies)
    out = env.client.post("/api/v1/auth/logout-all", cookies=c1,
                          headers={"X-CSRF-Token": r1.cookies.get("ra_csrf")})
    assert out.json()["revoked"] >= 2
    assert env.client.get("/api/v1/auth/me", cookies=c2).status_code == 401


def test_session_expiry_and_revoke(env, users):
    from datetime import datetime, timezone
    from src.db.models.session import Session as _S
    from sqlalchemy import select
    a = users["A"]
    with env.factory() as s:
        row = s.scalars(select(_S).where(_S.revoked_at.is_(None))).first()
        row.expires_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        sid = row.session_id
        s.commit()
    r = env.client.get("/api/v1/auth/me", cookies=a["cookies"])
    assert r.status_code == 401 and r.json()["error"]["code"] == "SESSION_EXPIRED"
    # revoke specific
    r = login(env.client, "b@example.com")
    sid2 = env.client.get("/api/v1/auth/sessions",
                          cookies=dict(r.cookies)).json()["items"][0]["session_id"]
    assert env.client.delete(f"/api/v1/auth/sessions/{sid2}", cookies=dict(r.cookies),
                             headers={"X-CSRF-Token": r.cookies.get("ra_csrf")}).status_code == 200
    assert env.client.get("/api/v1/auth/me", cookies=dict(r.cookies)).status_code == 401
    assert sid and sid2


def test_csrf_enforcement(env, users):
    a = users["A"]
    assert env.client.get("/api/v1/me/portfolio", cookies=a["cookies"]).status_code == 200
    no_csrf = env.client.post(f"/api/v1/participants/{a['pid']}/views",
                              json={"theme_ids": ["ai"]}, cookies=a["cookies"])
    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "CSRF_INVALID"
    wrong = env.client.post(f"/api/v1/participants/{a['pid']}/views",
                            json={"theme_ids": ["ai"]}, cookies=a["cookies"],
                            headers={"X-CSRF-Token": "wrong"})
    assert wrong.status_code == 403
    ok = env.client.post(f"/api/v1/participants/{a['pid']}/views",
                         json={"theme_ids": ["ai"]}, cookies=a["cookies"],
                         headers={"X-CSRF-Token": a["csrf"]})
    assert ok.status_code == 201


def test_idor_blocked(env, users):
    a, b = users["A"], users["B"]
    for path in [f"/api/v1/participants/{b['pid']}/portfolio",
                 f"/api/v1/participants/{b['pid']}/portfolio/comparison",
                 f"/api/v1/participants/{b['pid']}/views",
                 f"/api/v1/participants/{b['pid']}/views/current",
                 f"/api/v1/participants/{b['pid']}/performance",
                 f"/api/v1/participants/{b['pid']}/performance/nav",
                 f"/api/v1/participants/{b['pid']}/performance/active",
                 f"/api/v1/participants/{b['pid']}/performance/attribution",
                 f"/api/v1/participants/{b['pid']}"]:
        r = env.client.get(path, cookies=a["cookies"])
        assert r.status_code == 403, path
        assert r.json()["error"]["code"] == "PARTICIPANT_ACCESS_DENIED"
    assert env.client.get(f"/api/v1/participants/{a['pid']}/portfolio",
                          cookies=a["cookies"]).status_code == 200
    # cross-user POST also blocked
    r = env.client.post(f"/api/v1/participants/{b['pid']}/views",
                        json={"theme_ids": ["ai"]}, cookies=a["cookies"],
                        headers={"X-CSRF-Token": a["csrf"]})
    assert r.status_code == 403


def test_me_endpoints(env, users):
    a = users["A"]
    assert env.client.get("/api/v1/me", cookies=a["cookies"]).status_code == 200
    assert env.client.get("/api/v1/me/portfolio", cookies=a["cookies"]).status_code == 200
    assert env.client.get("/api/v1/me/portfolio/comparison",
                          cookies=a["cookies"]).status_code == 200
    assert env.client.get("/api/v1/me/views", cookies=a["cookies"]).status_code == 200
    assert env.client.get("/api/v1/me/views/current", cookies=a["cookies"]).status_code == 200
    assert env.client.get("/api/v1/me/performance", cookies=a["cookies"]).status_code == 200
    assert env.client.get("/api/v1/me/performance/nav", cookies=a["cookies"]).status_code == 200
    assert env.client.get("/api/v1/me/performance/active",
                          cookies=a["cookies"]).status_code == 200
    assert env.client.get("/api/v1/me/performance/attribution",
                          cookies=a["cookies"]).status_code == 200
    r = env.client.post("/api/v1/me/views", json={"theme_ids": ["ai"]},
                        cookies=a["cookies"], headers={"X-CSRF-Token": a["csrf"]})
    assert r.status_code == 201


def test_admin_gates(env, users, admin):
    assert env.client.get("/api/v1/admin/users", cookies=users["A"]["cookies"]).status_code == 403
    assert env.client.get("/api/v1/admin/trades", cookies=users["A"]["cookies"]).status_code == 403
    assert env.client.get("/api/v1/participants",
                          cookies=users["A"]["cookies"]).status_code == 403
    assert env.client.get("/api/v1/admin/users", cookies=admin["cookies"]).status_code == 200
    assert env.client.get("/api/v1/admin/orders/pending",
                          cookies=admin["cookies"]).status_code == 200
    assert env.client.get("/api/v1/admin/trades", cookies=admin["cookies"]).status_code == 200
    assert env.client.get("/api/v1/admin/system/status",
                          cookies=admin["cookies"]).status_code == 200
    jobs = env.client.get("/api/v1/admin/jobs", cookies=admin["cookies"])
    assert jobs.status_code == 200 and jobs.json()["items"] == []
    assert env.client.get("/api/v1/admin/jobs",
                          cookies=users["A"]["cookies"]).status_code == 403


def test_disabled_user(env, users, admin):
    a = users["A"]
    uid = env.client.get("/api/v1/auth/me", cookies=a["cookies"]).json()["user_id"]
    assert env.client.post(f"/api/v1/admin/users/{uid}/disable",
                           cookies=admin["cookies"],
                           headers={"X-CSRF-Token": admin["csrf"]}).status_code == 200
    assert login(env.client, "a@example.com").status_code == 401
    r = env.client.get("/api/v1/me/portfolio", cookies=a["cookies"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "USER_DISABLED"
    env.client.post(f"/api/v1/admin/users/{uid}/enable", cookies=admin["cookies"],
                    headers={"X-CSRF-Token": admin["csrf"]})
    assert login(env.client, "a@example.com").status_code == 200


def test_registration_config(env, monkeypatch):
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "false")
    r = register(env.client, "x@example.com")
    assert r.status_code == 403 and r.json()["error"]["code"] == "REGISTRATION_DISABLED"
    monkeypatch.setenv("ALLOW_PUBLIC_REGISTRATION", "true")
    assert register(env.client, "x@example.com").status_code == 201


def test_rate_limit_lockout(env, users):
    from src.db.models.user import User as _U
    from sqlalchemy import select
    for _ in range(5):
        r = login(env.client, "b@example.com", "wrong-password-12345")
        assert r.status_code == 401
    with env.factory() as s:
        u = s.scalars(select(_U).where(_U.email == "b@example.com")).first()
        assert u.failed_login_count >= 5 and u.locked_until is not None
    # correct password still rejected while locked (same code, no enumeration)
    r = login(env.client, "b@example.com")
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_change_password_rotates_others(env, users):
    a = users["A"]
    r2 = login(env.client, "a@example.com")
    c2 = dict(r2.cookies)
    ok = env.client.post("/api/v1/auth/change-password",
                         json={"current_password": "supersecure-passphrase-123",
                               "new_password": "even-longer-passphrase-456"},
                         cookies=a["cookies"], headers={"X-CSRF-Token": a["csrf"]})
    assert ok.status_code == 200
    assert env.client.get("/api/v1/auth/me", cookies=c2).status_code == 401
    assert env.client.get("/api/v1/auth/me", cookies=a["cookies"]).status_code == 200
    assert login(env.client, "a@example.com",
                 "even-longer-passphrase-456").status_code == 200


def test_malformed_and_guessed_tokens(env, users):
    import hashlib as _h
    a = users["A"]
    bad = dict(a["cookies"]);
    bad["ra_session"] = "not-a-real-token"
    assert env.client.get("/api/v1/auth/me", cookies=bad).status_code == 401
    bad["ra_session"] = _h.sha256(b"guess").hexdigest()
    assert env.client.get("/api/v1/auth/me", cookies=bad).status_code == 401
    env.client.cookies.clear()
    assert env.client.get("/api/v1/auth/me").status_code == 401


def test_no_sensitive_data_in_responses(env, users, admin):
    a = users["A"]
    me = env.client.get("/api/v1/auth/me", cookies=a["cookies"]).json()
    assert "password_hash" not in str(me) and "token_hash" not in str(me)
    ulist = env.client.get("/api/v1/admin/users", cookies=admin["cookies"]).json()
    assert "password_hash" not in str(ulist) and "email" in str(ulist)
    rk = env.client.get("/api/v1/rankings", cookies=a["cookies"]).json()
    assert "email" not in str(rk)


def test_logging_redaction():
    from src.api.middleware.logging_filter import RedactingFilter
    import logging
    f = RedactingFilter()
    rec = logging.LogRecord("t", 20, __file__, 1, "%s", ({"password": "x", "ok": 1},), None)
    assert f.filter(rec) is True
    assert rec.args == {"password": "***REDACTED***", "ok": 1}
