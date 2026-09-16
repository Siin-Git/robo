"""Interactive local test user creator (hidden password prompts)."""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["APP_PROFILE"] = "local"

from src.api.services import auth_service as auth  # noqa: E402
from src.db.session import session_factory  # noqa: E402
from src.forward.runtime import print_banner  # noqa: E402


def _prompt(prompt: str) -> str:
    return input(prompt).strip()


def _create(email: str, display_name: str, password: str, role: str = "user") -> dict:
    S = session_factory()
    with S() as s:
        user = auth.register(s, email, password, display_name, role=role)
        s.commit()
        return user


def main() -> int:
    print_banner("local")
    email = _prompt("Email: ")
    display = _prompt("Display Name: ")
    pw = getpass.getpass("Password (min 12 chars): ")
    confirm = getpass.getpass("Confirm Password: ")
    if pw != confirm:
        print("ERROR: passwords do not match.")
        return 2
    try:
        user = _create(email, display, pw, "user")
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    print(f"user created: {user['user_id']} ({user['email']}) -> {user['participant_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
