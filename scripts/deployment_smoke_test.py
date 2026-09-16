"""Deployment smoke test against real URLs (no local assumptions).

Env:
  FRONTEND_URL  e.g. https://app.vercel.app
  BACKEND_URL   e.g. https://api.onrender.com
  SMOKE_EMAIL / SMOKE_PASSWORD  dedicated deployment-test account (never logged)

Flow: frontend GET -> backend /health -> /ready -> login -> /auth/me ->
themes -> dashboard API (portfolio) -> logout. Any step failing exits non-zero.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar


def req(opener, method, url, data=None, headers=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method,
                               headers={"Content-Type": "application/json",
                                        **(headers or {})})
    try:
        with opener.open(r, timeout=60) as resp:
            return resp.status, resp.read().decode()[:2000]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def main() -> int:
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    backend = os.environ.get("BACKEND_URL", "").rstrip("/")
    email = os.environ.get("SMOKE_EMAIL", "")
    password = os.environ.get("SMOKE_PASSWORD", "")
    missing = [k for k, v in {"FRONTEND_URL": frontend, "BACKEND_URL": backend,
                              "SMOKE_EMAIL": email, "SMOKE_PASSWORD": password}.items() if not v]
    if missing:
        print(f"ERROR: missing env: {missing}")
        return 2
    steps = []
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")
        if not cond:
            ok = False

    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        with opener.open(frontend + "/", timeout=60) as r:
            check("frontend GET /", r.status == 200, str(r.status))
    except Exception as e:
        check("frontend GET /", False, str(e)[:120])
    s, _ = req(opener, "GET", backend + "/health")
    check("backend /health", s == 200, str(s))
    s, body = req(opener, "GET", backend + "/ready")
    check("backend /ready", s in (200, 503), f"{s} {body[:120]}")
    s, body = req(opener, "POST", backend + "/api/v1/auth/login",
                  {"email": email, "password": password})
    check("login", s == 200, str(s))
    names = {c.name for c in jar}
    check("session cookies", {"ra_session", "ra_csrf"} <= names, sorted(names))
    s, body = req(opener, "GET", backend + "/api/v1/auth/me")
    check("/auth/me", s == 200, body[:120])
    try:
        check("me has no secrets",
              "password_hash" not in body and "token_hash" not in body)
    except Exception:
        pass
    s, _ = req(opener, "GET", backend + "/api/v1/themes?active=true")
    check("themes", s == 200, str(s))
    s, _ = req(opener, "GET", backend + "/api/v1/me/portfolio")
    check("dashboard API (portfolio)", s in (200, 409), str(s))
    s, _ = req(opener, "POST", backend + "/api/v1/auth/logout", {})
    check("logout", s == 200, str(s))
    s, _ = req(opener, "GET", backend + "/api/v1/auth/me")
    check("post-logout denied", s == 401, str(s))
    print("SMOKE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
