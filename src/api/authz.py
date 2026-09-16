"""Authorization dependencies: current user, admin, ownership, CSRF.

Route handlers must use these — never ad-hoc role checks.
"""
from __future__ import annotations

from fastapi import Depends, Request

from .dependencies import get_db
from .errors import ApiError
from .services import auth_service as auth


def _cfg():
    from .services import _common as C
    return C.load_forward_cfg()


def get_current_user(request: Request, db=Depends(get_db)):
    raw = request.cookies.get(_cfg().get("auth", {}).get("cookie_name", "ra_session"))
    user, row, err = auth.authenticate(db, raw)
    if err == "AUTH_REQUIRED":
        raise ApiError("AUTH_REQUIRED", "Authentication required.", 401)
    if err == "SESSION_EXPIRED":
        raise ApiError("SESSION_EXPIRED", "Session has expired.", 401)
    if err == "SESSION_REVOKED":
        raise ApiError("SESSION_REVOKED", "Session has been revoked.", 401)
    if err == "USER_DISABLED":
        raise ApiError("USER_DISABLED", "User account is disabled.", 403)
    request.state.current_session_id = row.session_id
    return user


def require_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise ApiError("ADMIN_REQUIRED", "Admin role required.", 403)
    return user


def enforce_owner(user, participant_id: str):
    if user.role == "admin":
        return user
    if user.participant_id != participant_id:
        raise ApiError("PARTICIPANT_ACCESS_DENIED",
                       "You can only access your own participant data.", 403)
    return user


def require_owner(participant_id: str, user=Depends(get_current_user)):
    return enforce_owner(user, participant_id)


def require_csrf(request: Request, db=Depends(get_db), user=Depends(get_current_user)):
    """Double-submit CSRF: header token == cookie token == session record."""
    if request.method == "GET":
        return user
    raw = request.cookies.get(_cfg().get("auth", {}).get("cookie_name", "ra_session"))
    row = auth._lookup_session(db, raw)
    header = request.headers.get("X-CSRF-Token")
    cookie = request.cookies.get(_cfg().get("auth", {}).get("csrf_cookie_name", "ra_csrf"))
    if row is None or not auth.verify_csrf(row, header, cookie):
        raise ApiError("CSRF_INVALID", "Missing or invalid CSRF token.", 403)
    return user
