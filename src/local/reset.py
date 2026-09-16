"""Local DB reset: LOCAL ONLY, with confirmation."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ALLOWED = {str((ROOT / "data" / "forward_local.db").resolve())}


def main() -> int:
    from src.forward.runtime import get_database_path  # noqa: E402
    os.environ["APP_PROFILE"] = "local"
    db_path = get_database_path("local").resolve()
    if str(db_path) not in ALLOWED:
        print(f"ERROR: reset refused — path not in allowlist: {db_path}")
        return 2
    if not db_path.exists():
        print(f"Nothing to reset — no file at {db_path.relative_to(ROOT)}")
        return 0
    if "--yes" not in sys.argv:
        print("This will delete LOCAL data only.")
        print(f"  {db_path.relative_to(ROOT)}")
        ans = input("Continue? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Aborted.")
            return 0
    db_path.unlink()
    print(f"Deleted {db_path.relative_to(ROOT)}")
    print("Recreate with: python -m src.local.init")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
