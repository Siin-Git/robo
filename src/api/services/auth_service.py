"""Authentication service: Argon2id passwords, opaque sessions, CSRF, lockout.

No financial logic here. Passwords never stored; raw session/CSRF tokens never
stored (SHA-256 hashes only). All state changes are audited via events.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from ...db.repositories.forward import EventRepository, SessionRepository, UserRepository
from ..errors import ApiError
from . import _common as C
from .participant_service import create as _create_participant

_PH = None


def _hasher():
    global _PH
    if _PH is None:
        from argon2 import PasswordHasher
        _PH = PasswordHasher()
    return _PH


def _auth_cfg() -> dict:
    return C.load_forward_cfg().get("auth", {})


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_password(password: str) -> None:
    cfg = _auth_cfg()
    lo, hi = int(cfg.get("password_min_length", 12)), int(cfg.get("password_max_length", 128))
    if len(password or "") < lo:
        raise ApiError("PASSWORD_TOO_SHORT",
                       f"Password must be at least {lo} characters.", 422)
    if len(password or "") > hi:
        raise ApiError("PASSWORD_TOO_LONG",
                       f"Password must be at most {hi} characters.", 422)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now():
    return C.now_utc()


def _user_out(u) -> dict:
    return {"user_id": u.user_id, "email": u.email, "role": u.role,
            "status": u.status, "participant_id": u.participant_id}


def register(session, email: str, password: str, display_name: str,
             role: str = "user", participant_id: str | None = None,
             by_admin: bool = False) -> dict:
    users = UserRepository(session)
    norm = normalize_email(email)
    if not norm or "@" not in norm:
        raise ApiError("INVALID_EMAIL", "Email address is not valid.", 422)
    if users.by_email_normalized(norm) is not None:
        raise ApiError("EMAIL_ALREADY_EXISTS", "Email is already registered.", 409)
    validate_password(password)
    if role not in ("user", "admin"):
        raise ApiError("INVALID_ROLE", "role must be user or admin.", 422)
    pid = participant_id
    if pid is None:
        pid = _create_participant(session, display_name)["participant_id"]
    else:
        from ...db.models.participant import Participant as _P
        if session.get(_P, pid) is None:
            raise ApiError("PARTICIPANT_NOT_FOUND", f"Unknown participant {pid}.", 404)
        if users.by_participant(pid) is not None:
            raise ApiError("PARTICIPANT_ALREADY_LINKED",
                           f"Participant {pid} is already linked.", 409)
    uid = C.new_id(session, "U")
    users.add(user_id=uid, email=email.strip(), email_normalized=norm,
              password_hash=_hasher().hash(password), role=role, status="active",
              participant_id=pid, failed_login_count=0, locked_until=None,
              created_at=_now(), updated_at=_now(), last_login_at=None,
              password_changed_at=_now())
    C.log_event(session, "USER_CREATED_BY_ADMIN" if by_admin else "USER_REGISTERED",
                C.load_forward_cfg()["forward_test"]["benchmark_version"], participant_id=pid,
                payload={"user_id": uid, "email": norm, "role": role})
    C.log_event(session, "USER_PARTICIPANT_LINKED",
                C.load_forward_cfg()["forward_test"]["benchmark_version"], participant_id=pid,
                payload={"user_id": uid})
    session.flush()
    return _user_out(users.get(uid))


def _fail_login(session, u, cfg) -> None:
    u.failed_login_count = int(u.failed_login_count or 0) + 1
    if u.failed_login_count >= int(cfg.get("max_failed_logins", 5)):
        u.locked_until = _now() + timedelta(minutes=int(cfg.get("lockout_minutes", 15)))
    u.updated_at = _now()
    session.flush()
    # Persist even though the request itself fails (the outer transaction rolls
    # back on the 401 path); otherwise brute-force counting would never stick.
    session.commit()


def _invalid():
    return ApiError("INVALID_CREDENTIALS", "Invalid email or password.", 401)


def login(session, email: str, password: str, user_agent: str | None = None) -> tuple[dict, str, str]:
    cfg = _auth_cfg()
    ft = C.load_forward_cfg()["forward_test"]
    users = UserRepository(session)
    u = users.by_email_normalized(normalize_email(email))
    if u is None:
        raise _invalid()
    if u.locked_until is not None and C.as_aware_utc(u.locked_until) > _now():
        raise _invalid()
    try:
        ok = _hasher().verify(u.password_hash, password or "")
    except Exception:
        ok = False
    if not ok:
        _fail_login(session, u, cfg)
        raise _invalid()
    if u.status != "active":
        raise _invalid()
    u.failed_login_count = 0
    u.locked_until = None
    u.last_login_at = _now()
    u.updated_at = _now()
    raw_session, raw_csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    sid = C.new_id(session, "S", 6)
    ttl = int(cfg.get("session_ttl_days", 7))
    SessionRepository(session).add(
        session_id=sid, user_id=u.user_id, token_hash=hash_token(raw_session),
        csrf_token_hash=hash_token(raw_csrf), created_at=_now(),
        expires_at=_now() + timedelta(days=ttl), last_seen_at=_now(),
        revoked_at=None, user_agent=(user_agent or "")[:512])
    C.log_event(session, "USER_LOGGED_IN", ft["benchmark_version"], participant_id=u.participant_id,
                payload={"user_id": u.user_id})
    session.flush()
    return _user_out(u), raw_session, raw_csrf


def _lookup_session(session, raw_token):
    if not raw_token:
        return None
    return SessionRepository(session).by_token_hash(hash_token(raw_token))


def authenticate(session, raw_token):
    """Return (user, session_row, error_code). Never raises for bad tokens."""
    row = _lookup_session(session, raw_token)
    if row is None:
        # indistinguishable: wrong token vs guessed hash
        return None, None, "AUTH_REQUIRED"
    if row.revoked_at is not None:
        return None, row, "SESSION_REVOKED"
    if C.as_aware_utc(row.expires_at) <= _now():
        return None, row, "SESSION_EXPIRED"
    users = UserRepository(session)
    u = users.get(row.user_id)
    if u is None or u.status != "active":
        return None, row, "USER_DISABLED"
    row.last_seen_at = _now()
    session.flush()
    return u, row, None


def logout(session, row) -> None:
    row.revoked_at = _now()
    C.log_event(session, "USER_LOGGED_OUT",
                C.load_forward_cfg()["forward_test"]["benchmark_version"],
                participant_id=row.user.participant_id if row.user else None,
                payload={"session_id": row.session_id})
    session.flush()


def logout_all(session, user) -> int:
    n = 0
    for r in SessionRepository(session).active_for(user.user_id):
        r.revoked_at = _now()
        n += 1
    C.log_event(session, "USER_LOGGED_OUT_ALL",
                C.load_forward_cfg()["forward_test"]["benchmark_version"],
                participant_id=user.participant_id,
                payload={"user_id": user.user_id, "revoked": n})
    session.flush()
    return n


def revoke_session(session, user, session_id: str) -> None:
    from ...db.models.session import Session as _S
    row = session.get(_S, session_id)
    if row is None or row.user_id != user.user_id:
        raise ApiError("SESSION_NOT_FOUND", "Unknown session.", 404)
    if row.revoked_at is None:
        row.revoked_at = _now()
        C.log_event(session, "SESSION_REVOKED",
                    C.load_forward_cfg()["forward_test"]["benchmark_version"],
                    participant_id=user.participant_id,
                    payload={"session_id": session_id})
    session.flush()


def list_sessions(session, user, current_id: str | None) -> list[dict]:
    out = []
    for r in SessionRepository(session).active_for(user.user_id):
        out.append({"session_id": r.session_id,
                    "created_at": C.as_aware_utc(r.created_at),
                    "last_seen_at": C.as_aware_utc(r.last_seen_at),
                    "expires_at": C.as_aware_utc(r.expires_at),
                    "current": r.session_id == current_id})
    return out


def change_password(session, user, current_password: str, new_password: str,
                    keep_session_id: str) -> None:
    try:
        ok = _hasher().verify(user.password_hash, current_password or "")
    except Exception:
        ok = False
    if not ok:
        raise _invalid()
    validate_password(new_password)
    user.password_hash = _hasher().hash(new_password)
    user.password_changed_at = _now()
    user.updated_at = _now()
    # Policy: revoke every other session, keep the current one. Documented.
    for r in SessionRepository(session).active_for(user.user_id):
        if r.session_id != keep_session_id:
            r.revoked_at = _now()
    C.log_event(session, "PASSWORD_CHANGED",
                C.load_forward_cfg()["forward_test"]["benchmark_version"],
                participant_id=user.participant_id, payload={"user_id": user.user_id})
    session.flush()


def verify_csrf(session_row, header_token: str | None, cookie_token: str | None) -> bool:
    if not header_token or not cookie_token:
        return False
    if not hmac.compare_digest(header_token, cookie_token):
        return False
    return hmac.compare_digest(hash_token(cookie_token), session_row.csrf_token_hash or "")


def disable_user(session, user_id: str) -> dict:
    from ...db.models.user import User as _U
    u = session.get(_U, user_id)
    if u is None:
        raise ApiError("USER_NOT_FOUND", f"Unknown user {user_id}.", 404)
    u.status = "disabled"
    u.updated_at = _now()
    C.log_event(session, "USER_DISABLED",
                C.load_forward_cfg()["forward_test"]["benchmark_version"],
                participant_id=u.participant_id, payload={"user_id": user_id})
    session.flush()
    return _user_out(u)


def enable_user(session, user_id: str) -> dict:
    from ...db.models.user import User as _U
    u = session.get(_U, user_id)
    if u is None:
        raise ApiError("USER_NOT_FOUND", f"Unknown user {user_id}.", 404)
    u.status = "active"
    u.failed_login_count = 0
    u.locked_until = None
    u.updated_at = _now()
    C.log_event(session, "USER_ENABLED",
                C.load_forward_cfg()["forward_test"]["benchmark_version"],
                participant_id=u.participant_id, payload={"user_id": user_id})
    session.flush()
    return _user_out(u)
