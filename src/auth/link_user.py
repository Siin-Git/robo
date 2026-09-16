"""Link an existing user to an existing participant (one-to-one enforced)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.services import _common as C  # noqa: E402
from src.api.services import auth_service as auth  # noqa: E402
from src.db.repositories.forward import UserRepository  # noqa: E402
from src.db.session import session_factory  # noqa: E402
from src.forward.runtime import print_banner  # noqa: E402


def main() -> int:
    print_banner()
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--participant", required=True)
    args = ap.parse_args()
    S = session_factory()
    with S() as s:
        try:
            u = UserRepository(s).by_email_normalized(auth.normalize_email(args.email))
            if u is None:
                print(f"ERROR: unknown user {args.email}")
                return 1
            from src.db.models.participant import Participant as _P
            if s.get(_P, args.participant) is None:
                print(f"ERROR: unknown participant {args.participant}")
                return 1
            if UserRepository(s).by_participant(args.participant) is not None:
                print(f"ERROR: participant {args.participant} is already linked.")
                return 1
            u.participant_id = args.participant
            u.updated_at = C.now_utc()
            C.log_event(s, "USER_PARTICIPANT_LINKED",
                        C.load_forward_cfg()["forward_test"]["benchmark_version"],
                        participant_id=args.participant,
                        payload={"user_id": u.user_id})
            s.commit()
        except Exception as e:
            s.rollback()
            print(f"ERROR: {e}")
            return 1
    print(f"linked {args.email} -> {args.participant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
