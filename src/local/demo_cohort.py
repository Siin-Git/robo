"""Explicit, non-destructive rehearsal setup. Never called by startup/seed.

python -m src.local.demo_cohort --name rehearsal-01 --email presenter@example.com --out /private/tmp/rehearsal-invites.json
Use two --email arguments for (COHORT_SIZE - 2) prepared + 2 reserved slots. A new name creates
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
from .capstone import enabled, COHORT_SIZE, EMAILS


def prepare(session, name, emails, *, invitation_hashes=None):
    if not enabled() or session.get_bind().dialect.name != "sqlite":
        raise ValueError("Only the isolated local capstone SQLite demo is supported.")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", name):
        raise ValueError("Use a unique 1–48 character rehearsal name.")
    emails = [auth.normalize_email(e) for e in emails]
    if len(emails) not in (1, 2) or len(set(emails)) != len(emails) or any("@" not in e for e in emails):
        raise ValueError("Provide one or two distinct reserved emails.")
    if invitation_hashes is not None and (len(invitation_hashes) != len(emails)
            or len(set(invitation_hashes)) != len(invitation_hashes)
            or any(not re.fullmatch(r"[a-f0-9]{64}", h) for h in invitation_hashes)):
        raise ValueError("Provide distinct SHA-256 invitation hashes, one per email.")
    if session.get(DemoCohort, name):
        raise ValueError("Rehearsal already exists; use a new name. Existing data is never reset.")
    if session.scalar(select(User).where(User.email_normalized.in_(emails))):
        raise ValueError("Use new reserved emails; existing accounts cannot be reassigned.")
    if len(list(session.scalars(select(User).where(User.email_normalized.in_(EMAILS))))) != COHORT_SIZE:
        raise ValueError("Run the existing capstone seed first.")
    session.add(DemoCohort(cohort_id=name, prepared_count=COHORT_SIZE-len(emails), created_at=C.now_utc()))
    session.flush()
    invitations = []
    for i, email in enumerate(emails, 1):
        token = secrets.token_urlsafe(32) if invitation_hashes is None else None
        session.add(DemoSlot(slot_id=f"{name}:{i}", cohort_id=name, slot_number=i,
            invite_hash=auth.hash_token(token) if token else invitation_hashes[i-1], email_normalized=email, draft_json={}))
        invitations.append({"email": email, **({"invitation_code": token} if token else {})})
    state = session.get(ForwardState, svc.ACTIVE_KEY)
    if state:
        state.value, state.updated_at = name, C.now_utc()
    else:
        session.add(ForwardState(key=svc.ACTIVE_KEY, value=name, updated_at=C.now_utc()))
    session.flush()
    return {"cohort_id": name, "capacity": COHORT_SIZE, "prepared": COHORT_SIZE-len(emails), "invitations": invitations}


def prepare_from_environment(session):
    """Explicit server-side provisioning; replay never resets a claimed slot.

    CAPSTONE_INVITATIONS_JSON contains cohort_id and invitations with email and
    invite_sha256. Raw invitation codes remain with the operator, never in logs.
    This is NOT called from API startup, signup or seed.
    """
    if not enabled() or session.get_bind().dialect.name != "sqlite":
        raise ValueError("Server invitations require the isolated capstone SQLite profile.")
    try:
        data = json.loads(os.environ["CAPSTONE_INVITATIONS_JSON"])
        name = data["cohort_id"]
        entries = data["invitations"]
        emails = [auth.normalize_email(e["email"]) for e in entries]
        hashes = [e["invite_sha256"] for e in entries]
        valid = (isinstance(name, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", name)
                 and len(emails) in (1, 2) and len(set(emails)) == len(emails)
                 and all("@" in e for e in emails) and len(set(hashes)) == len(hashes)
                 and all(isinstance(h, str) and re.fullmatch(r"[a-f0-9]{64}", h) for h in hashes))
        if not valid:
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("Invalid CAPSTONE_INVITATIONS_JSON; expected cohort_id and 1–2 unique email/invite_sha256 entries.") from None
    group = session.get(DemoCohort, name)
    if group is not None:
        expected = list(zip(emails, hashes))
        existing = sorted(svc.slots(session, group), key=lambda s: s.slot_number)
        active = svc.active(session)
        if (group.prepared_count != COHORT_SIZE-len(emails)
                or [(s.email_normalized, s.invite_hash) for s in existing] != expected
                or active is None or active.cohort_id != name):
            raise ValueError("Invitation configuration differs from the saved cohort; no data was changed.")
        return {"cohort_id": name, "prepared": group.prepared_count, "unchanged": True}
    if svc.active(session) is not None:
        raise ValueError("An active cohort already exists; use the explicit local preparation command for a new rehearsal.")
    result = prepare(session, name, emails, invitation_hashes=hashes)
    return {"cohort_id": name, "prepared": result["prepared"], "unchanged": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name")
    parser.add_argument("--email", action="append")
    parser.add_argument("--out", type=Path, help="Private untracked invite file (mode 0600)")
    parser.add_argument("--from-env", action="store_true", help="Explicit, idempotent import from server-only CAPSTONE_INVITATIONS_JSON")
    args = parser.parse_args()
    if not enabled():
        parser.error("Set APP_PROFILE=local CAPSTONE_DEMO=1 DATABASE_BACKEND=sqlite explicitly.")
    from ..db.session import create_app_engine, session_factory
    from ..db.config import ROOT
    if args.from_env and any([args.name, args.email, args.out]):
        parser.error("Use either --from-env or --name/--email/--out.")
    if not args.from_env and not all([args.name, args.email, args.out]):
        parser.error("Local preparation requires --name, --email and --out.")
    target = args.out.resolve() if args.out else None
    if target and target.is_relative_to(ROOT.parent):
        parser.error("Invitation files must be outside the repository.")
    engine = create_app_engine()
    if engine.dialect.name != "sqlite":
        parser.error("Invitation provisioning never migrates the production database.")
    # Additive demo-only tables. No production migrations or existing data changes.
    DemoCohort.__table__.create(engine, checkfirst=True)
    DemoSlot.__table__.create(engine, checkfirst=True)
    with session_factory(engine)() as session:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        if args.from_env:
            try:
                data = prepare_from_environment(session)
                session.commit()
            except ValueError as error:
                parser.error(str(error))
            print("Server invitation cohort unchanged." if data["unchanged"] else "Server invitation cohort prepared.")
            return
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
