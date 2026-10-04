"""Small shared-start gate over the existing cohort and operating state.

No prices, positions or performance are manufactured here. Auth supplies the
roster; immutable operating decisions prove readiness. The explicit schedule
freezes those initial decisions and gives every account the same KST floor.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, time
from functools import wraps
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, select, text

from src.db.config import capstone_mode, get_database_url

KST = ZoneInfo("Asia/Seoul")
START_KEY = "competition_start"
MEMBER_PREFIX = "competition_member:"
_batch = ContextVar("competition_batch", default=None)


class StartError(RuntimeError):
    """Safe error code, deliberately without connection details."""


def now_kst():
    return datetime.now(KST)


def read_cohort():
    """Read auth only; never create a missing SQLite database or schema."""
    from sqlalchemy.engine import make_url
    from src.db.session import create_app_engine
    from src.db.models import User
    from src.db.models.demo_cohort import DemoCohort, DemoSlot
    from src.db.models.operational import ForwardState
    from src.local.capstone import COHORT_SIZE, EMAILS

    engine = None
    try:
        url = get_database_url()
        parsed = make_url(url)
        if parsed.get_backend_name() == "sqlite" and not Path(parsed.database or "").is_file():
            raise StartError("COHORT_DATABASE_UNAVAILABLE")
        engine = create_app_engine(url)
        with engine.connect() as con:
            if engine.dialect.name == "postgresql":
                con.execute(text("SET TRANSACTION READ ONLY"))
            else:
                con.execute(text("PRAGMA query_only=ON"))
            if not inspect(con).has_table("forward_state"):
                raise StartError("COHORT_SCHEMA_MISSING")
            cohort_id = con.execute(select(ForwardState.value).where(
                ForwardState.key == "demo_active_cohort")).scalar()
            if not cohort_id:
                return None  # Unmanaged, pre-existing non-competition operation.
            group = con.execute(select(DemoCohort).where(DemoCohort.cohort_id == cohort_id)).mappings().first()
            if not group:
                raise StartError("COHORT_NOT_FOUND")
            slots = con.execute(select(DemoSlot).where(DemoSlot.cohort_id == cohort_id)
                                .order_by(DemoSlot.slot_number)).mappings().all()
            users = {u["user_id"]: u for u in con.execute(select(
                User.user_id, User.participant_id, User.status, User.role, User.email_normalized)).mappings()}
            members = []
            for slot in slots:
                user = users.get(slot["user_id"])
                members.append({"user_id": slot["user_id"],
                    "participant_id": user["participant_id"] if user else None,
                    "confirmed": bool(slot["confirmed_at"]),
                    "active": bool(user and user["status"] == "active" and user["role"] == "user")})
            for email in EMAILS[:group["prepared_count"]]:
                user = next((u for u in users.values() if u["email_normalized"] == email), None)
                members.append({"user_id": user["user_id"] if user else None,
                    "participant_id": user["participant_id"] if user else None,
                    "confirmed": True,
                    "active": bool(user and user["status"] == "active" and user["role"] == "user")})
            return {"cohort_id": cohort_id, "required": COHORT_SIZE, "members": members}
    except StartError:
        raise
    except Exception:
        raise StartError("COHORT_READ_FAILED") from None
    finally:
        if engine is not None:
            engine.dispose()


def saved_start(con):
    if hasattr(con, "_con"):
        if con.execute("SELECT to_regclass('forward_state') t").fetchone()["t"] is None:
            return None
    elif not con.execute("SELECT name FROM sqlite_master WHERE name='forward_state'").fetchone():
        return None
    row = con.execute("SELECT value FROM forward_state WHERE key=?", (START_KEY,)).fetchone()
    if not row:
        return None
    saved = json.loads(row["value"])
    saved["members"] = []
    for row in con.execute("SELECT value FROM forward_state WHERE key LIKE ? ORDER BY key", (MEMBER_PREFIX + "%",)).fetchall():
        m = json.loads(row["value"])
        saved["members"].append({"user_id": m["u"], "participant_id": m["p"],
            "personal_account_id": m["a"], "account_ids": [m["a"], m["c"]], "decision_id": m["d"]})
    return saved


def readiness(con, cohort):
    from src.forward.decision_policy import latest_decision
    members = []
    for person in cohort["members"]:
        pid = person["participant_id"]
        accounts = [dict(r) for r in con.execute(
            "SELECT * FROM accounts WHERE participant_id=? AND status='active'", (pid,)).fetchall()] if pid else []
        personal = next((a for a in accounts if a["account_type"] == "personal"), None)
        core = next((a for a in accounts if a["account_type"] == "core"), None)
        decision = latest_decision(con, personal["account_id"]) if personal else None
        ready = bool(person["active"] and person["confirmed"] and personal and core and decision
                     and decision["user_id"] == person["user_id"] and decision["participant_id"] == pid)
        members.append({"user_id": person["user_id"], "participant_id": pid,
            "status": "READY" if ready else "NOT_READY",
            "account_ids": [a["account_id"] for a in (personal, core) if a],
            "personal_account_id": personal["account_id"] if personal else None,
            "decision_id": decision["decision_id"] if ready else None,
            "effective_date": str(decision["effective_date"])[:10] if ready else None})
    count = sum(m["status"] == "READY" for m in members)
    ids = [m["participant_id"] for m in members]
    all_ready = len(members) == cohort["required"] == count and len(set(ids)) == len(ids)
    return members, count, all_ready


def policy(con):
    """Fail closed for an active cohort, including APP_PROFILE=local Actions."""
    cached = _batch.get()
    if cached is not None and cached[0] is con:
        return cached[1]
    # Persisted policy remains authoritative even if a profile flag is removed.
    try:
        stored = saved_start(con)
        if not capstone_mode() and not stored:
            return {"managed": False, "blocked": False, "start_date": None}
        cohort = read_cohort()
        if cohort is None:
            if stored:
                raise StartError("COHORT_NOT_FOUND")
            return {"managed": False, "blocked": False, "start_date": None}
        members, count, ready = readiness(con, cohort)
        result = {"managed": True, "blocked": True, "reason": "PARTICIPANTS_NOT_READY",
            "cohort_id": cohort["cohort_id"], "ready": count, "required": cohort["required"],
            "members": members, "start_date": stored["start_date"] if stored else None,
            "status": "READY" if ready else "NOT_READY", "schedule": stored}
        if not ready:
            return result
        if not stored:
            result["reason"] = "START_NOT_SCHEDULED"
            return result
        roster = {(m["user_id"], m["participant_id"], tuple(sorted(m["account_ids"]))) for m in members}
        planned = {(m["user_id"], m["participant_id"], tuple(sorted(m["account_ids"]))) for m in stored["members"]}
        if stored["cohort_id"] != cohort["cohort_id"] or roster != planned or stored["required"] != cohort["required"]:
            result["reason"] = "COHORT_CHANGED"
            return result
        for member in stored["members"]:
            initial = con.execute("SELECT * FROM portfolio_decisions WHERE decision_id=?", (member["decision_id"],)).fetchone()
            if (not initial or initial["user_id"] != member["user_id"]
                    or initial["participant_id"] != member["participant_id"]
                    or initial["account_id"] != member["personal_account_id"]
                    or str(initial["effective_date"])[:10] > stored["start_date"]):
                result["reason"] = "START_DECISION_UNAVAILABLE"
                return result
        inception = con.execute("SELECT value FROM forward_state WHERE key='forward_test_inception_at'").fetchone()
        if not inception or inception["value"] != stored["start_at"]:
            result["reason"] = "INCEPTION_MISMATCH"
            return result
        if now_kst() < datetime.fromisoformat(stored["start_at"]):
            result["reason"] = "AWAITING_T0"
            return result
        result.update(blocked=False, reason=None, status="STARTED")
        return result
    except StartError as error:
        return {"managed": True, "blocked": True, "reason": str(error), "start_date": None}
    except (KeyError, ValueError, TypeError):
        return {"managed": True, "blocked": True, "reason": "INVALID_START_STATE", "start_date": None}


@contextmanager
def batch_guard(con):
    current = policy(con)
    token = _batch.set((con, current))
    try:
        yield current
    finally:
        _batch.reset(token)


def guarded_batch(function):
    @wraps(function)
    def run(con, *args, **kwargs):
        with batch_guard(con):
            return function(con, *args, **kwargs)
    return run


def account_gate(con, account_id):
    current = policy(con)
    if not current["managed"]:
        return False, None
    if current["blocked"]:
        return True, current.get("start_date")
    enrolled = {a for m in current["schedule"]["members"] for a in m["account_ids"]}
    return account_id not in enrolled, current["start_date"]


def initial_decision(con, account_id):
    current = policy(con)
    if not current["managed"] or current["blocked"]:
        return None
    member = next((m for m in current["schedule"]["members"] if m["personal_account_id"] == account_id), None)
    row = con.execute("SELECT * FROM portfolio_decisions WHERE decision_id=?",
                      (member["decision_id"],)).fetchone() if member else None
    return dict(row) if row else None


def schedule_start(con, start_date):
    """Explicit operator command. No overwrite, cleanup, trades, or backfill."""
    if not capstone_mode():
        raise StartError("COHORT_PROFILE_REQUIRED")
    day = date.fromisoformat(start_date)
    cohort = read_cohort()
    if cohort is None:
        raise StartError("COHORT_NOT_FOUND")
    previous = saved_start(con)
    if previous:
        if previous["cohort_id"] == cohort["cohort_id"] and previous["start_date"] == day.isoformat():
            return previous
        raise StartError("START_ALREADY_SCHEDULED")
    if day <= now_kst().date():
        raise StartError("PAST_T0_FORBIDDEN")
    members, _, ready = readiness(con, cohort)
    if not ready:
        raise StartError("PARTICIPANTS_NOT_READY")
    if any(m["effective_date"] > day.isoformat() for m in members):
        raise StartError("T0_BEFORE_DECISION_EFFECTIVE_DATE")
    from src.forward.state import get_state
    if get_state(con, "forward_test_inception_at") or get_state(con, "first_execution_at"):
        raise StartError("FORWARD_ALREADY_STARTED")
    accounts = {a for m in members for a in m["account_ids"]}
    capitals = {float(con.execute("SELECT initial_capital_krw FROM accounts WHERE account_id=?",
                                 (account_id,)).fetchone()["initial_capital_krw"]) for account_id in accounts}
    if len(capitals) != 1 or any(not math.isfinite(amount) or amount <= 0 for amount in capitals):
        raise StartError("INITIAL_CAPITAL_MISMATCH")
    for account_id in accounts:
        for table in ("trades", "holdings_daily", "nav_daily"):
            if con.execute(f"SELECT 1 FROM {table} WHERE account_id=? LIMIT 1", (account_id,)).fetchone():
                raise StartError("EXISTING_OPERATING_HISTORY")
        from src.forward.decision_policy import weights
        personal = next((m for m in members if m["personal_account_id"] == account_id), None)
        if personal:
            row = con.execute("SELECT * FROM portfolio_decisions WHERE decision_id=?", (personal["decision_id"],)).fetchone()
            expected = weights(dict(row))
        else:
            from src.forward.config import load_forward_config, resolve
            from src.forward.frozen import load_frozen_benchmark
            expected, _ = load_frozen_benchmark(resolve(load_forward_config()["frozen_dir"]))
        pending = con.execute("SELECT * FROM orders WHERE account_id=? AND status='pending'", (account_id,)).fetchall()
        assets = set()
        for order in pending:
            if (order["asset_id"] in assets or order["side"] != "buy"
                    or abs(float(order["target_weight"]) - float(expected.get(order["asset_id"], 0))) > 1e-9
                    or str(order["effective_at"])[:10] > day.isoformat()):
                raise StartError("PENDING_INITIAL_ORDER_CONFLICT")
            assets.add(order["asset_id"])
    stamp = now_kst().isoformat()
    start_at = datetime.combine(day, time.min, KST).isoformat()
    saved = {"cohort_id": cohort["cohort_id"], "required": cohort["required"],
        "start_date": day.isoformat(), "start_at": start_at, "scheduled_at": stamp}
    values = [(START_KEY, json.dumps(saved, separators=(",", ":"))), ("forward_test_inception_at", start_at)]
    for member in members:
        core = next(a for a in member["account_ids"] if a != member["personal_account_id"])
        values.append((MEMBER_PREFIX + member["user_id"], json.dumps({
            "u": member["user_id"], "p": member["participant_id"], "a": member["personal_account_id"],
            "c": core, "d": member["decision_id"]}, separators=(",", ":"))))
    if any(len(key) > 64 or len(value) > 256 for key, value in values):
        raise StartError("STATE_IDENTIFIER_TOO_LONG")
    # Metadata, member references and inception commit together. A concurrent
    # schedule loses the primary-key race and rolls back the whole policy.
    try:
        for key, value in values:
            con.execute("INSERT INTO forward_state (key,value,updated_at) VALUES (?,?,?)", (key, value, stamp))
        con.commit()
    except Exception:
        con.rollback()
        raise StartError("START_WRITE_CONFLICT") from None
    return saved_start(con)


def main():
    import argparse
    from src.forward.db import connect
    from src.forward.runtime import get_database_path, print_banner
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", help="Explicit shared date YYYY-MM-DD (KST); omit for status only")
    args = parser.parse_args()
    print_banner()
    con = connect(get_database_path())
    try:
        if args.start_date:
            schedule_start(con, args.start_date)
        current = policy(con)
        print(json.dumps(current, ensure_ascii=False))
        return 0
    except (StartError, ValueError) as error:
        print(f"Competition start refused: {error if isinstance(error, StartError) else 'INVALID_T0'}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
