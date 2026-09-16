"""Create an admin user (password via hidden prompt, never CLI args)."""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.services import auth_service as auth  # noqa: E402
from src.db.session import session_factory  # noqa: E402
from src.forward.runtime import get_database_path, print_banner  # noqa: E402


def main() -> int:
    print_banner()
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    args = ap.parse_args()
    password = getpass.getpass("Admin password (min 12 chars): ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("ERROR: passwords do not match.")
        return 2
    S = session_factory()
    with S() as s:
        try:
            user = auth.register(s, args.email, password, display_name="Administrator",
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
