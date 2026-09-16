"""Interactive local admin creator (hidden password prompts)."""
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


def main() -> int:
    print_banner("local")
    email = input("Email: ").strip()
    pw = getpass.getpass("Admin password (min 12 chars): ")
    confirm = getpass.getpass("Confirm password: ")
    if pw != confirm:
        print("ERROR: passwords do not match.")
        return 2
    S = session_factory()
    with S() as s:
        try:
            user = auth.register(s, email, pw, display_name="Administrator",
                                 role="admin", participant_id=None)
            s.commit()
        except Exception as e:
            s.rollback()
            print(f"ERROR: {e}")
            return 1
    print(f"admin created: {user['user_id']} ({user['email']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
