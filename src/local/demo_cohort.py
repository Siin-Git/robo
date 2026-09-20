"""Explicit, non-destructive rehearsal setup. Never called by startup/seed.

python -m src.local.demo_cohort --name rehearsal-01 --email presenter@example.com --out /private/tmp/rehearsal-invites.json
Use two --email arguments for 11 prepared + 2 reserved slots. A new name creates
another rehearsal without deleting users, configurations or historical results.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
from sqlalchemy import select
from ..api.services import enrollment_service as svc, auth_service as auth, _common as C
from ..db.models.demo_cohort import DemoCohort, DemoSlot
from ..db.models.operational import ForwardState
from ..db.models.user import User
from .capstone import enabled, EMAILS


def prepare(session, name, emails):
    if not enabled() or session.get_bind().dialect.name != "sqlite":
        raise ValueError("Only the isolated local capstone SQLite demo is supported.")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", name):
        raise ValueError("Use a unique 1–48 character rehearsal name.")
    emails = [auth.normalize_email(e) for e in emails]
    if len(emails) not in (1, 2) or len(set(emails)) != len(emails) or any("@" not in e for e in emails):
        raise ValueError("Provide one or two distinct reserved emails.")
    if session.get(DemoCohort, name):
        raise ValueError("Rehearsal already exists; use a new name. Existing data is never reset.")
    if session.scalar(select(User).where(User.email_normalized.in_(emails))):
        raise ValueError("Use new reserved emails; existing accounts cannot be reassigned.")
    if len(list(session.scalars(select(User).where(User.email_normalized.in_(EMAILS))))) != 13:
        raise ValueError("Run the existing capstone seed first.")
    session.add(DemoCohort(cohort_id=name, prepared_count=13-len(emails), created_at=C.now_utc()))
    session.flush()
    invitations = []
    for i, email in enumerate(emails, 1):
        token = secrets.token_urlsafe(32)
        session.add(DemoSlot(slot_id=f"{name}:{i}", cohort_id=name, slot_number=i,
            invite_hash=auth.hash_token(token), email_normalized=email, draft_json={}))
        invitations.append({"email": email, "invitation_code": token})
    state = session.get(ForwardState, svc.ACTIVE_KEY)
    if state:
        state.value, state.updated_at = name, C.now_utc()
    else:
        session.add(ForwardState(key=svc.ACTIVE_KEY, value=name, updated_at=C.now_utc()))
    session.flush()
    return {"cohort_id": name, "capacity": 13, "prepared": 13-len(emails), "invitations": invitations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True, help="Private untracked invite file (mode 0600)")
    args = parser.parse_args()
    if not enabled():
        parser.error("Set APP_PROFILE=local CAPSTONE_DEMO=1 DATABASE_BACKEND=sqlite explicitly.")
    from ..db.session import create_app_engine, session_factory
    from ..db.config import ROOT
    target = args.out.resolve()
    if target.is_relative_to(ROOT.parent):
        parser.error("Invitation files must be outside the repository.")
    engine = create_app_engine()
    # Additive demo-only tables. No production migrations or existing data changes.
    DemoCohort.__table__.create(engine, checkfirst=True)
    DemoSlot.__table__.create(engine, checkfirst=True)
    with session_factory(engine)() as session:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        data = prepare(session, args.name, args.email)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            session.commit()
        except Exception:
            target.unlink(missing_ok=True)
            raise
    print(f"Prepared {data['prepared']} + {len(args.email)} reserved. Private invitations: {target}")


if __name__ == "__main__":
    main()
