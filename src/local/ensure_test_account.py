"""Ensure LOCAL test accounts exist (LOCAL only, never other profiles)."""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Force LOCAL for this helper even if caller didn't set it (safety: only local path).
os.environ["APP_PROFILE"] = "local"
os.environ.setdefault("DATABASE_BACKEND", "sqlite")

from src.api.services import auth_service as auth  # noqa: E402
from src.db.repositories.forward import UserRepository  # noqa: E402
from src.db.session import session_factory  # noqa: E402


def _ensure_one(email_env: str, pw_env: str, name_env: str,
                default_email: str, default_name: str, role: str) -> tuple[str, str | None, bool]:
    """Returns (email, password_to_display_or_None, created)."""
    email = os.environ.get(email_env, default_email).strip() or default_email
    display = os.environ.get(name_env, default_name).strip() or default_name
    # Check existing first — never overwrite password.
    S = session_factory()
    with S() as s:
        if UserRepository(s).by_email_normalized(auth.normalize_email(email)) is not None:
            return email, None, False
    # Not existing — need a password.
    password = os.environ.get(pw_env, "").strip()
    generated = False
    if not password:
        # LOCAL-only fallback: generate once, show in console, never store plaintext.
        password = secrets.token_urlsafe(16)  # ~21 chars, satisfies 12-min rule
        generated = True
    S2 = session_factory()
    with S2() as s:
        try:
            auth.register(s, email, password, display, role=role)
            s.commit()
        except Exception as e:
            # Race: another start_local created it first.
            if "already" in str(e).lower():
                return email, None, False
            raise
    return email, (password if generated else None), True


def ensure_local_test_accounts() -> dict:
    """Create localtest + optional localadmin if missing (LOCAL only)."""
    if os.environ.get("APP_PROFILE", "local").strip().lower() != "local":
        return {}
    out: dict = {}
    email, pw, created = _ensure_one(
        "LOCAL_TEST_EMAIL", "LOCAL_TEST_PASSWORD", "LOCAL_TEST_DISPLAY_NAME",
        "localtest@example.com", "Local Test User", "user")
    out["user"] = {"email": email, "password": pw, "created": created}
    # Admin is optional: only if env requests it (or explicit email set).
    admin_email_env = os.environ.get("LOCAL_ADMIN_EMAIL", "").strip()
    admin_pw_env = os.environ.get("LOCAL_ADMIN_PASSWORD", "").strip()
    # Also support default admin if password was provided via env but email not overridden.
    want_admin = bool(admin_email_env or admin_pw_env)
    # For convenience in local preview, also auto-create default admin if user explicitly
    # set LOCAL_ADMIN_PASSWORD without email — use default email.
    if want_admin:
        a_email, a_pw, a_created = _ensure_one(
            "LOCAL_ADMIN_EMAIL", "LOCAL_ADMIN_PASSWORD", "LOCAL_ADMIN_DISPLAY_NAME",
            "localadmin@example.com", "Local Admin", "admin")
        out["admin"] = {"email": a_email, "password": a_pw, "created": a_created}
    return out


def print_banner(accounts: dict) -> None:
    for key in ("user", "admin"):
        if key not in accounts:
            continue
        info = accounts[key]
        if info["created"]:
            label = "LOCAL TEST ACCOUNT READY" if key == "user" else "LOCAL ADMIN ACCOUNT READY"
            print(f"\n{label}\n")
            print(f"Email:\n{info['email']}\n")
            if info["password"] is not None:
                print(f"Temporary Password:\n{info['password']}\n")
            else:
                print("Password: (from environment)\n")
            print("URL:\nhttp://localhost:3000/login\n")
        else:
            print(f"existing local {'test user' if key=='user' else 'admin'} found: {info['email']}")


if __name__ == "__main__":
    accts = ensure_local_test_accounts()
    print_banner(accts)
