"""Auth routes: register / login / logout / sessions / password."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from ..authz import get_current_user, require_admin
from ..dependencies import get_db
from ..errors import ApiError
from ..services import auth_service as auth

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: str
    password: str
    display_name: str = Field(min_length=1, max_length=128)


class LoginBody(BaseModel):
    email: str
    password: str


class PasswordBody(BaseModel):
    current_password: str
    new_password: str


def _cookie_conf():
    from ..services import _common as C
    cfg = C.load_forward_cfg().get("auth", {})
    secure = os.environ.get("APP_PROFILE", "live").strip().lower() == "live"
    override = os.environ.get("AUTH_COOKIE_SECURE", "").strip().lower()
    if override in ("1", "true", "yes"):
        secure = True
    elif override in ("0", "false", "no"):
        secure = False
    return cfg.get("cookie_name", "ra_session"), cfg.get("csrf_cookie_name", "ra_csrf"), \
        int(cfg.get("session_ttl_days", 7)) * 86400, secure


def _set_auth_cookies(resp: Response, raw_session: str, raw_csrf: str) -> None:
    sname, cname, max_age, secure = _cookie_conf()
    resp.set_cookie(sname, raw_session, max_age=max_age, httponly=True, secure=secure,
                    samesite="lax", path="/")
    resp.set_cookie(cname, raw_csrf, max_age=max_age, httponly=False, secure=secure,
                    samesite="lax", path="/")


def _clear_auth_cookies(resp: Response) -> None:
    sname, cname, _, _ = _cookie_conf()
    resp.delete_cookie(sname, path="/")
    resp.delete_cookie(cname, path="/")


def _registration_allowed() -> bool:
    from ...local.capstone import enabled
    if enabled():
        return False
    if os.environ.get("APP_PROFILE", "").strip().lower() == "local":
        return True
    return os.environ.get("ALLOW_PUBLIC_REGISTRATION", "false").strip().lower() == "true"


@router.post("/register", status_code=201, summary="Public registration (config-gated)")
def register(body: RegisterBody, db=Depends(get_db)):
    if not _registration_allowed():
        raise ApiError("REGISTRATION_DISABLED", "Public registration is disabled.", 403)
    return auth.register(db, body.email, body.password, body.display_name)


@router.post("/login", summary="Login (sets session + CSRF cookies)")
def login(body: LoginBody, request: Request, response: Response, db=Depends(get_db)):
    user, raw_session, raw_csrf = auth.login(
        db, body.email, body.password,
        (request.headers.get("user-agent") or "")[:512])
    _set_auth_cookies(response, raw_session, raw_csrf)
    return {"user": user}


@router.post("/logout", summary="Revoke current session")
def logout(request: Request, response: Response, db=Depends(get_db),
           user=Depends(get_current_user)):
    from ..services import _common as C
    raw = request.cookies.get(C.load_forward_cfg().get("auth", {}).get("cookie_name",
                                                                       "ra_session"))
    row = auth._lookup_session(db, raw)
    if row is not None:
        auth.logout(db, row)
    _clear_auth_cookies(response)
    return {"ok": True}


@router.post("/logout-all", summary="Revoke all own sessions")
def logout_all(response: Response, db=Depends(get_db), user=Depends(get_current_user)):
    n = auth.logout_all(db, user)
    _clear_auth_cookies(response)
    return {"ok": True, "revoked": n}


@router.get("/me", summary="Current user + participant")
def me(db=Depends(get_db), user=Depends(get_current_user)):
    out = {"user_id": user.user_id, "email": user.email, "role": user.role,
           "status": user.status, "participant_id": user.participant_id}
    if user.participant_id:
        from ...db.models.participant import Participant as _P
        p = db.get(_P, user.participant_id)
        out["display_name"] = p.display_name if p else None
    else:
        out["display_name"] = None
    return out


@router.get("/sessions", summary="Own active sessions (no raw tokens)")
def my_sessions(request: Request, db=Depends(get_db), user=Depends(get_current_user)):
    return {"items": auth.list_sessions(db, user, getattr(request.state,
                                                          "current_session_id", None))}


@router.delete("/sessions/{session_id}", summary="Revoke one own session")
def revoke_session(session_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    auth.revoke_session(db, user, session_id)
    return {"ok": True}


@router.post("/change-password", summary="Change password (revokes other sessions)")
def change_password(body: PasswordBody, request: Request, db=Depends(get_db),
                    user=Depends(get_current_user)):
    auth.change_password(db, user, body.current_password, body.new_password,
                         getattr(request.state, "current_session_id", ""))
    return {"ok": True, "policy": "other sessions revoked, current session kept"}
