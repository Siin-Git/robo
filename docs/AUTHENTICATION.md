# Authentication (Phase 3C)

> WARNING: no MFA, no email verification, no password reset (by design, see
> below). Do not expose publicly without HTTPS/reverse proxy (Phase 3D+).

## Method

- Passwords: **Argon2id** (`argon2-cffi`), 12–128 chars, no composition rules.
  Plaintext never stored; identical passwords get different hashes (random salt).
- Sessions: **opaque server-side** (`secrets.token_urlsafe(32)`); only
  **SHA-256 hashes** in DB. Cookies: `ra_session` (HttpOnly) + readable
  `ra_csrf`; `SameSite=Lax`, `Path=/`, `Secure` iff `APP_PROFILE=live`
  (overridable via `AUTH_COOKIE_SECURE=0` for local HTTP).
- CSRF: double-submit — `X-CSRF-Token` header must equal the CSRF cookie and
  match the session's stored hash. Required on all POST/PUT/PATCH/DELETE
  except login/register; GETs exempt.
- Lifetime: 7-day server-side expiry (`auth.session_ttl_days`); rotation on
  every login; password change revokes all other sessions.
- Lockout: 5 consecutive failures → 15-minute lock
  (`auth.max_failed_logins` / `lockout_minutes`); responses stay
  `INVALID_CREDENTIALS` (no enumeration, no timing oracle beyond hashing).

## Roles & ownership

- Roles: `user`, `admin` (no RBAC framework). One user ↔ at most one
  participant (`users.participant_id` unique, nullable for admins).
- Dependencies: `get_current_user()` / `require_admin()` /
  `require_owner()` (+ `enforce_owner`); no ad-hoc role checks in routes.
- Users see only their own participant subtree (views, portfolio,
  comparison, performance, NAV, attribution, detail) — 403 otherwise, even
  for unknown IDs. Rankings expose display names + performance only.
- `/api/v1/me/*` mirrors owner endpoints without needing participant IDs.
- Participant CRUD is admin-only; admin user/benchmark/system routes are
  admin-only; `/health`, `/ready`, `/version` stay public.

## Registration

`ALLOW_PUBLIC_REGISTRATION` (default `false`; demo may set `true`).
Registration creates participant + accounts + core targets + user + link +
audit events in one transaction. Team provisioning without public
registration: `python -m src.auth.create_user` / `create_admin` (passwords via
hidden prompt, never CLI args) / `link_user` (existing participant, dup-link
refused).

## Sessions & password APIs

`POST /auth/login|logout|logout-all`, `GET /auth/me|sessions`,
`DELETE /auth/sessions/{id}`, `POST /auth/change-password`.
Logout revokes (rows kept). Disabled users: login fails, live sessions go
403 `USER_DISABLED`. No forgot-password flow (no email provider — later phase).

## Audit events

`USER_REGISTERED`, `USER_CREATED_BY_ADMIN`, `USER_LOGGED_IN/OUT/OUT_ALL`,
`PASSWORD_CHANGED`, `USER_DISABLED/ENABLED`, `SESSION_REVOKED`,
`USER_PARTICIPANT_LINKED` — never carrying tokens or passwords.

## Docs & contract

- `docs/API_AUTH_MATRIX.md` (per-endpoint Public/User/Admin matrix)
- OpenAPI regenerated: `outputs/api/openapi_v1.json`
