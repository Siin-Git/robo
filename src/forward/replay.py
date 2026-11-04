"""Explicit, local-only counterfactual execution scope over the existing engine.

The source design DB and its confirmation/effective dates are never changed.
Only this disposable run's connection can use its historical calendar. Outside
the scope account_gate refuses the replay ledger, even to the daily CLI.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile

KIND = "HISTORICAL_REPLAY"
LABEL = "현재 확정 구성을 과거 시장 가격에 적용한 모의실험"
_scope = ContextVar("isolated_replay", default=None)


def local_directory(directory):
    directory = Path(directory).resolve()
    roots = (Path('/private/tmp'), Path(tempfile.gettempdir()).resolve())
    if not any(directory.is_relative_to(root) for root in roots):
        raise ValueError("Replay requires a separate disposable local directory")
    marker = json.loads((directory / "local-replay.json").read_text())
    if marker.get("kind") != "LOCAL_COMPETITION_REPLAY" or (directory / "operation.json").exists():
        raise ValueError("Not a replay directory; existing operation is preserved")
    return directory


def connection_directory(con):
    if not isinstance(con, sqlite3.Connection):
        return None
    files = [r[2] for r in con.execute("PRAGMA database_list") if r[1] == "main"]
    if not files or not files[0]:
        return None
    path = Path(files[0]).resolve()
    if path.name != "replay_ledger.db" or not (path.parent / "local-replay.json").exists():
        return None
    return local_directory(path.parent)


def manifest(directory):
    directory = local_directory(directory)
    value = json.loads((directory / "run.json").read_text())
    if value.get("kind") != KIND or value.get("required") != 15:
        raise ValueError("Invalid replay run")
    return value


def state(con, key):
    row = con.execute("SELECT value FROM forward_state WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def save_state(con, key, value):
    con.execute("INSERT OR REPLACE INTO forward_state (key,value,updated_at) VALUES (?,?,?)",
                (key, str(value), datetime.now(timezone.utc).isoformat()))
    con.commit()


def default_guard(con):
    directory = connection_directory(con)
    if directory is None:
        return None
    current = _scope.get()
    if current and current["connection"] is con and current["mode"] == "FORWARD_VALIDATION":
        return None  # Original future-T0 policy applies, without changing its clock.
    return {"managed": True, "blocked": True, "status": "REPLAY_ONLY",
            "reason": "REPLAY_SCOPED_EXECUTION_REQUIRED", "start_date": None}


def scoped_policy(con):
    current = _scope.get()
    return current["policy"] if current and current["connection"] is con and current["mode"] == KIND else None


def inception_floor(con):
    current = scoped_policy(con)
    return current["start_date"] if current else None


@contextmanager
def exclusive(directory):
    import fcntl  # Local replay is POSIX-only; ordinary Windows operation still imports.
    directory = local_directory(directory)
    with (directory / "competition-run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("This competition run is already executing") from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def execution_scope(con, mode=KIND):
    from . import competition as gate
    directory = connection_directory(con)
    if directory is None or os.environ.get("DATABASE_BACKEND") != "sqlite":
        raise ValueError("Historical execution is allowed only on the marked local replay ledger")
    from src.db.config import get_database_url
    from sqlalchemy.engine import make_url
    if Path(make_url(get_database_url()).database).resolve().parent != directory:
        raise ValueError("Replay roster must use this run's separate local auth DB")
    run = manifest(directory)
    if state(con, "replay_run_id") != run["run_id"] or state(con, "replay_manifest_sha256") != sha256((directory / "run.json").read_bytes()).hexdigest():
        raise ValueError("Replay identity or manifest changed")
    cohort = gate.read_cohort()
    members, count, ready = gate.readiness(con, cohort) if cohort else ([], 0, False)
    expected = {(m["user_id"], m["decision_id"]) for m in run["members"]}
    if not ready or count != run["required"] or expected != {(m["user_id"], m["decision_id"]) for m in members}:
        raise ValueError("All original replay participants must remain READY with their captured decisions")
    if mode == "FORWARD_VALIDATION":
        marker = json.loads((directory / "local-replay.json").read_text())
        if not marker.get("forward_validation_copy") or state(con, "replay_status") != "COMPLETE":
            raise ValueError("Forward validation requires a separate completed-run copy")
    elif mode != KIND:
        raise ValueError("Unknown execution scope")
    policy = {"managed": True, "blocked": False, "status": KIND, "start_date": run["start"],
              "schedule": {"members": members}, "ready": count, "required": run["required"], "reason": None}
    token = _scope.set({"connection": con, "mode": mode, "policy": policy})
    try:
        yield run
    finally:
        _scope.reset(token)


def verify_completed(con, run):
    dates = set(run["dates"])
    completed = 0
    for member in run["members"]:
        valid = True
        for aid in member["account_ids"]:
            rows = con.execute("SELECT date,nav,cash_balance,nav_status FROM nav_daily WHERE account_id=? AND date>=? AND date<=?",
                               (aid, run["start"], run["end"])).fetchall()
            if {r["date"] for r in rows} != dates:
                valid = False
            for row in rows:
                if row["nav_status"] != "OK" or row["nav"] is None or float(row["nav"]) <= 0:
                    valid = False
                held = con.execute("SELECT COALESCE(SUM(market_value),0) FROM holdings_daily WHERE account_id=? AND date=?",
                                   (aid, row["date"])).fetchone()[0]
                if abs(float(held) + float(row["cash_balance"]) - float(row["nav"])) > 1e-5:
                    raise RuntimeError("Replay accounting identity failed")
            if not con.execute("SELECT 1 FROM trades WHERE account_id=?", (aid,)).fetchone():
                valid = False
        completed += valid
    return completed


def execute(directory, fail_after=None):
    """Checkpointed engine replay. fail_after is for isolated recovery tests only."""
    from .accounts import versions_from_cfg, record_target
    from .config import load_forward_config
    from .execution import create_orders, execute_pending
    from .ledger import valuate
    from .db import log_event
    directory = local_directory(directory)
    cfg = load_forward_config(); ft = cfg["forward_test"]; versions = versions_from_cfg(cfg)
    with exclusive(directory), sqlite3.connect(directory / "replay_ledger.db") as con:
        con.row_factory = sqlite3.Row
        with execution_scope(con) as run:
            completed = verify_completed(con, run)
            if state(con, "replay_status") == "COMPLETE":
                if completed != run["required"]:
                    save_state(con, "replay_status", "INCOMPLETE")
                    raise RuntimeError("Completed-run ledger is incomplete")
                return {"status": "COMPLETE", "completed": completed, "reused": True}
            save_state(con, "replay_status", "RUNNING")
            visited = 0
            try:
                for day in run["dates"]:
                    for member in run["members"]:
                        for aid in member["account_ids"]:
                            if state(con, "replay_progress:" + aid) and state(con, "replay_progress:" + aid) >= day:
                                continue
                            targets = run["weights"][aid]
                            # Require exact observations: no engine fallback to an earlier date.
                            for asset, weight in targets.items():
                                if asset != "cash" and weight > 0 and not con.execute(
                                        "SELECT 1 FROM prices_daily WHERE asset_id=? AND date=?", (asset, day)).fetchone():
                                    raise RuntimeError(f"Missing replay price: {asset} {day}")
                            if day == run["start"]:
                                record_target(con, aid, targets, day, "HISTORICAL_REPLAY", versions,
                                              ft["benchmark_version"], member["participant_id"])
                                # A crash after fills but before the NAV checkpoint must
                                # not submit the initial buys a second time.
                                existing = con.execute("SELECT 1 FROM orders WHERE account_id=? AND effective_at=?",
                                                       (aid, day)).fetchone()
                                if not existing:
                                    create_orders(con, aid, targets, day + "T00:00:00+09:00", day,
                                                  ft["benchmark_version"], member["participant_id"], kind=KIND, baseline={})
                                if aid == member["personal_account_id"]:
                                    event = "DECISION_ORDER:" + member["decision_id"]
                                    if not con.execute("SELECT 1 FROM events WHERE event_type=? AND account_id=?", (event, aid)).fetchone():
                                        log_event(con, event, ft["benchmark_version"], member["participant_id"], aid,
                                                  {"run_id": run["run_id"], "execution_kind": KIND})
                                        con.commit()
                            execute_pending(con, aid, day, float(ft["costs"]["trading_cost_bps"]),
                                            ft["benchmark_version"], member["participant_id"])
                            result = valuate(con, aid, day, versions, float(run["initial_capital_krw"]))
                            if result["status"] != "OK":
                                raise RuntimeError(f"Replay valuation incomplete: {aid} {day}")
                            if con.execute("SELECT 1 FROM orders WHERE account_id=? AND status='pending'", (aid,)).fetchone():
                                raise RuntimeError(f"Replay pending execution incomplete: {aid} {day}")
                            save_state(con, "replay_progress:" + aid, day)
                            visited += 1
                            if fail_after is not None and visited == fail_after:
                                raise RuntimeError("Injected recovery-test interruption")
                completed = verify_completed(con, run)
                if completed != run["required"]:
                    raise RuntimeError("Not all competition participants completed")
                save_state(con, "replay_status", "COMPLETE")
                return {"status": "COMPLETE", "completed": completed, "reused": False}
            except Exception:
                save_state(con, "replay_status", "INCOMPLETE")
                raise


def read_metadata(session):
    """A read contract; original decision reviews always use the design DB."""
    from src.db.models.operational import ForwardState
    from sqlalchemy import select
    bind = session.get_bind()
    if bind.dialect.name != "sqlite" or Path(bind.url.database or "").name != "replay_ledger.db":
        return None
    row = session.get(ForwardState, "replay_run_id")
    if row is None:
        return None
    directory = Path(session.get_bind().url.database).resolve().parent
    run = manifest(directory)
    fingerprint = session.get(ForwardState, "replay_manifest_sha256")
    if row.value != run["run_id"] or not fingerprint or fingerprint.value != sha256((directory / "run.json").read_bytes()).hexdigest():
        raise ValueError("Replay run mismatch")
    status = session.get(ForwardState, "replay_status").value
    completed = 0
    from src.db.models.nav import NavDaily
    for member in run["members"]:
        complete = all(set(session.scalars(select(NavDaily.date).where(
            NavDaily.account_id == aid)).all()) >= {date.fromisoformat(d) for d in run["dates"]}
            for aid in member["account_ids"])
        completed += complete
    # Date coverage alone cannot certify usable valuations or accounting.
    with sqlite3.connect(directory / "replay_ledger.db") as con:
        con.row_factory = sqlite3.Row
        try:
            completed = min(completed, verify_completed(con, run))
        except (RuntimeError, TypeError, ValueError):
            completed = 0
    if completed != run["required"] and status == "COMPLETE":
        status = "INCOMPLETE"
    return {"run_id": run["run_id"], "kind": KIND, "label": LABEL, "status": status,
            "ready": run["required"], "required": run["required"], "completed": completed,
            "start": run["start"], "end": run["end"], "dates": run["dates"],
            "forward_start": run["forward_start"], "forward_started": False,
            "initial_capital_krw": run["initial_capital_krw"], "price_basis": run["price_basis"],
            "excluded_dates": run.get("excluded_dates", [])}
