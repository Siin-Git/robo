"""Provision the cohort's independent, unconfigured participants in an isolated lab DB.

인원수는 src/local/capstone.py 의 COHORT 하나에서만 정한다.
"""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import secrets

import yaml
from sqlalchemy import select

from .capstone import COHORT_SIZE, EMAILS, enabled
from ..api.services import auth_service as auth, enrollment_service as enrollment, _common as C
from ..db.models.demo_cohort import DemoCohort, DemoSlot
from ..db.models.operational import ForwardState
from ..db.models.theme import Theme
from ..db.models.user import User


def prepare(session, name, passwords=None, *, password_hashes=None):
    """A repeated invocation preserves identities, passwords, drafts and results."""
    from ..api.services.market_comparison import enabled as market_enabled
    if not enabled() or not market_enabled() or session.get_bind().dialect.name != "sqlite":
        raise ValueError("Use the isolated local SQLite market-comparison profile.")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", name):
        raise ValueError("Use a 1–48 character lab meeting name.")
    group = enrollment.active(session)
    if group:
        slots = sorted(enrollment.slots(session, group), key=lambda s: s.slot_number)
        if (group.cohort_id != name or group.prepared_count != 0 or len(slots) != COHORT_SIZE
                or [s.email_normalized for s in slots] != EMAILS
                or any(not s.user_id or session.get(User, s.user_id).email_normalized != s.email_normalized for s in slots)):
            raise ValueError("This database belongs to another cohort; use a new data directory.")
        return False
    if session.scalar(select(User.user_id).limit(1)) or session.scalar(select(DemoCohort.cohort_id).limit(1)):
        raise ValueError("Lab preparation requires an empty database; existing accounts are never reassigned.")
    if password_hashes is not None:
        if passwords is not None:
            raise ValueError("Provide either passwords or server-side hashes.")
        validate_hashes(password_hashes)
    else:
        if passwords is None or set(passwords) != set(EMAILS) or len(set(passwords.values())) != COHORT_SIZE:
            raise ValueError("Provide one distinct password per participant.")
        for password in passwords.values():
            auth.validate_password(password)
    with (C.ROOT / "config/themes_v01.yaml").open(encoding="utf-8") as f:
        for item in yaml.safe_load(f)["themes"]:
            if session.get(Theme, item["theme_id"]) is not None:
                continue
            data = {k: v for k, v in item.items() if k in Theme.__table__.columns.keys()}
            for key in ("valid_from", "valid_to"):
                if isinstance(data.get(key), str):
                    data[key] = date.fromisoformat(data[key])
            session.add(Theme(**data))
    session.add(DemoCohort(cohort_id=name, prepared_count=0, created_at=C.now_utc()))
    session.flush()
    for i, email in enumerate(EMAILS, 1):
        # A server import never needs the participants' plaintext passwords.
        user = auth.register(session, email, passwords[email] if passwords else secrets.token_urlsafe(32),
            f"참여자 {i:02d}", by_admin=True)
        if password_hashes:
            session.get(User, user["user_id"]).password_hash = password_hashes[email]
        session.add(DemoSlot(slot_id=f"{name}:{i}", cohort_id=name, slot_number=i,
            email_normalized=email, user_id=user["user_id"],
            invite_hash=auth.hash_token(secrets.token_urlsafe(32)),
            draft_json={"core_id": "CORE_V0.3", "theme_ids": [], "reason": "", "current_step": "risk"}))
    session.add(ForwardState(key=enrollment.ACTIVE_KEY, value=name, updated_at=C.now_utc()))
    session.flush()
    return True


def validate_hashes(hashes):
    from argon2 import extract_parameters, Type
    try:
        if set(hashes) != set(EMAILS) or len(set(hashes.values())) != COHORT_SIZE:
            raise ValueError()
        for value in hashes.values():
            p = extract_parameters(value)
            if (p.type != Type.ID or p.version != 19 or p.hash_len < 16 or p.salt_len < 16
                    or not 19456 <= p.memory_cost <= 262144 or not 1 <= p.time_cost <= 10
                    or not 1 <= p.parallelism <= 8):
                raise ValueError()
    except Exception:
        raise ValueError(f"Provide {COHORT_SIZE} distinct valid Argon2id hashes for the lab accounts.") from None


def prepare_from_environment(session):
    """Idempotent server bootstrap from a private Render environment variable."""
    try:
        data = json.loads(os.environ["CAPSTONE_LAB_ACCOUNTS_JSON"])
        name = data["cohort_id"]
        entries = data["accounts"]
        if (not isinstance(name, str) or not isinstance(entries, list) or len(entries) != COHORT_SIZE
                or any(set(e) != {"email", "password_hash"} for e in entries)):
            raise ValueError()
        hashes = {auth.normalize_email(e["email"]): e["password_hash"] for e in entries}
        validate_hashes(hashes)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError(f"Invalid CAPSTONE_LAB_ACCOUNTS_JSON: expected cohort_id and {COHORT_SIZE} email/password_hash entries.") from None
    return prepare(session, name, password_hashes=hashes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name")
    parser.add_argument("--out", type=Path, help="Private, untracked account list (.json)")
    parser.add_argument("--from-env", action="store_true", help="Import server-only account hashes; never export passwords")
    args = parser.parse_args()
    if args.from_env and (args.name or args.out):
        parser.error("Use either --from-env or --name/--out.")
    if not args.from_env and not args.out:
        parser.error("Local preparation requires --out.")
    from ..db.config import get_database_url, ROOT
    from ..db.session import create_app_engine, session_factory
    from ..db.base import Base
    from sqlalchemy.engine import make_url
    from ..api.services.market_comparison import enabled as market_enabled
    if not enabled() or not market_enabled() or os.environ.get("DATABASE_BACKEND") != "sqlite":
        parser.error("Set APP_PROFILE=local CAPSTONE_DEMO=1 CAPSTONE_MARKET_COMPARISON=1 DATABASE_BACKEND=sqlite.")
    directory = os.environ.get("CAPSTONE_DATA_DIR")
    if not directory or Path(directory).resolve() == (ROOT / "data").resolve():
        parser.error("Set CAPSTONE_DATA_DIR to a separate lab meeting directory.")
    url = get_database_url()
    if make_url(url).get_backend_name() != "sqlite":
        parser.error("Only the local SQLite database is supported.")
    Path(make_url(url).database).parent.mkdir(parents=True, exist_ok=True)
    target = args.out.resolve() if args.out else None
    if target and (target.suffix != ".json" or (target.is_relative_to(ROOT.parent) and not target.is_relative_to(ROOT / ".work"))):
        parser.error("Account files must be outside the repository or inside ignored .work, with a .json extension.")
    if target:
        target.parent.mkdir(parents=True, exist_ok=True)
    engine = create_app_engine(url)
    Base.metadata.create_all(engine)
    created_files = []
    with session_factory(engine)() as session:
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        if args.from_env:
            try:
                created = prepare_from_environment(session)
                session.commit()
            except ValueError as error:
                parser.error(str(error))
            print(f"{COHORT_SIZE} server lab accounts prepared." if created else "Existing server lab accounts and selections preserved.")
            return
        passwords = {email: secrets.token_urlsafe(12) for email in EMAILS}
        try:
            name = args.name or "lab-meeting"
            created = prepare(session, name, passwords)
            if created:
                accounts = [{"number": i, "email": e, "password": passwords[e]} for i, e in enumerate(EMAILS, 1)]
                document = "# 랩미팅 참가자 계정\n\n참가자에게 본인의 한 행만 전달하세요. 기존 데모 공통 비밀번호와 다릅니다.\n\n"
                document += "| 번호 | 아이디 | 초기 비밀번호 |\n| --- | --- | --- |\n"
                document += "\n".join(f"| {a['number']:02d} | {a['email']} | `{a['password']}` |" for a in accounts) + "\n"
                for path, content in ((target, json.dumps({"cohort_id": name, "accounts": accounts}, ensure_ascii=False, indent=2)),
                                      (target.with_suffix(".md"), document)):
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    created_files.append(path)
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(content)
            session.commit()
        except Exception:
            for path in created_files:
                path.unlink(missing_ok=True)
            raise
    print(f"{COHORT_SIZE} lab accounts prepared; no selections or historical NAV assigned." if created else "Existing lab accounts and selections preserved.")
    print(f"Private account list: {target.with_suffix('.md')}")


if __name__ == "__main__":
    main()
