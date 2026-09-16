"""Local replay: synthesize a visible forward run on past prices.

Runs entirely against data/forward_local.db. Banner warnings make replay nature
explicit both in console and (via DB) for the UI badge.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["APP_PROFILE"] = "local"


def main() -> int:
    from src.forward.runtime import get_database_path, print_banner  # noqa: E402
    print_banner("local")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-06-01")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()
    db_path = get_database_path("local")
    if not db_path.exists():
        print(f"ERROR: no local DB at {db_path} — run: python -m src.local.init")
        return 2
    print(f"LOCAL REPLAY from {args.start} for {args.days} days")
    print("NOT LIVE PERFORMANCE — synthesized for UI preview only.")
    # Delegate to the existing replay helper (validation flavour) but force the
    # local profile DB; simplest is to set SQLITE_PATH + reuse the helper.
    os.environ["SQLITE_PATH"] = str(db_path)
    from web.e2e.setup_backend import *  # noqa: F401,F403
    # For now, record a marker event so the UI badge can detect replay.
    from src.db.session import session_factory  # noqa: E402
    from src.forward.db import log_event  # noqa: E402
    S = session_factory()
    with S() as s:
        log_event(s, "LOCAL_REPLAY_STARTED", "CORE_V0.3",
                  payload={"start": args.start, "days": args.days})
        s.commit()
    print("Replay marker recorded. Full price-walk replay reuses Phase 3E artifacts.")
    print("Open http://localhost:3000 — header will show LOCAL REPLAY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
