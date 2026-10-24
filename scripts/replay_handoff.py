"""Plan with read-only production input, replay in a disposable child, apply by hash.

No raw account data is uploaded or logged. The existing Actions runner owns the
short-lived plan; only the aggregate receipt and checksum leave it.
"""
import argparse
from contextlib import closing
from datetime import date
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.forward.handoff import digest, snapshot, validate_plan, apply, audit


def replay_local(input_path, output_path):
    """Runs with production URLs removed and the marked local replay DB only."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from src.db.base import Base
    import src.db.models  # register all tables
    from src.forward import replay
    from src.forward.config import load_forward_config
    from src.forward.accounts import record_target, versions_from_cfg
    from src.forward.execution import create_orders, execute_pending
    from src.forward.ledger import valuate
    from src.api.services.ledger_read_service import ledger
    source = json.loads(Path(input_path).read_text())
    directory = Path(os.environ["CAPSTONE_DATA_DIR"])
    fingerprint = digest(source)
    stamp = source["end"] + "T00:00:00+09:00"
    (directory / "local-replay.json").write_text(json.dumps({"kind": "LOCAL_COMPETITION_REPLAY"}))
    decisions = {d["decision_id"]: d for d in source["decisions"]}
    def insert(con, table, row):
        columns = list(row)
        con.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    tuple(json.dumps(row[c]) if isinstance(row[c], (dict, list)) else row[c] for c in columns))
    for filename in ("capstone_demo.db", "replay_ledger.db"):
        engine = create_engine(f"sqlite:///{directory / filename}")
        Base.metadata.create_all(engine)
        engine.dispose()
        with sqlite3.connect(directory / filename) as con:
            for p in source["participants"]:
                insert(con, "participants", p)
            insert(con, "demo_cohorts", dict(cohort_id="handoff", prepared_count=0, created_at=stamp))
            for i, member in enumerate(source["members"]):
                d = decisions[member["decision_id"]]
                email = member["participant_id"].lower() + "@replay.invalid"
                insert(con, "users", dict(user_id=member["user_id"], participant_id=member["participant_id"],
                    email=email, email_normalized=email, password_hash="!NO_LOGIN_REPLAY", role="user", status="active",
                    failed_login_count=0, created_at=stamp, updated_at=stamp))
                insert(con, "demo_slots", dict(slot_id=f"handoff-{i}", cohort_id="handoff", slot_number=i+1,
                    invite_hash=digest(member), email_normalized=email, user_id=member["user_id"], draft_json={}, confirmed_at=d["confirmed_at"]))
            replay.save_state(con, "demo_active_cohort", "handoff")
            if filename == "replay_ledger.db":
                for table, key in (("accounts", "accounts"), ("portfolio_decisions", "decisions"), ("prices_daily", "prices")):
                    for row in source[key]:
                        insert(con, table, row)
            con.commit()
    cfg = load_forward_config()
    if cfg["forward_test"] != source["config"]:
        raise ValueError("ENGINE_CONFIG_CHANGED")
    versions = versions_from_cfg(cfg)
    weights = {aid: decisions[m["decision_id"]]["weights_json"] if aid == m["personal_account_id"] else source["core"]
               for m in source["members"] for aid in m["account_ids"]}
    required_assets = {a for w in weights.values() for a, value in w.items() if value > 0 and a != "cash"}
    # Every initial order must have a real close on the same first valuation day.
    dates_by_asset = {a: {p["date"] for p in source["prices"] if p["asset_id"] == a} for a in required_assets}
    common = sorted(set.intersection(*dates_by_asset.values()))
    if not common:
        raise ValueError("NO_COMMON_INITIAL_PRICE_DATE")
    first = common[0]
    days = sorted({p["date"] for p in source["prices"] if p["date"] >= first and date.fromisoformat(p["date"]).weekday() < 5})
    if len(days) < 2 or (date.fromisoformat(source["end"]) - date.fromisoformat(days[-1])).days > 4:
        raise ValueError("INSUFFICIENT_RECENT_REPLAY_PRICES")
    run = dict(kind="HISTORICAL_REPLAY", run_id=fingerprint, required=15, members=source["members"],
               start=first, end=days[-1], dates=days, weights=weights, forward_start=source["forward_start"],
               price_basis="RECORDED_MARKET_PRICES", initial_capital_krw=source["accounts"][0]["initial_capital_krw"])
    encoded = json.dumps(run, sort_keys=True)
    (directory / "run.json").write_text(encoded)
    with closing(sqlite3.connect(directory / "replay_ledger.db")) as con:
        con.row_factory = sqlite3.Row
        replay.save_state(con, "replay_run_id", fingerprint)
        from hashlib import sha256
        replay.save_state(con, "replay_manifest_sha256", sha256(encoded.encode()).hexdigest())
        replay.save_state(con, "replay_status", "PREPARED")
        with replay.execution_scope(con):
            for day in days:
                for m in source["members"]:
                    for aid in m["account_ids"]:
                        if day == first:
                            record_target(con, aid, weights[aid], day, "HISTORICAL_REPLAY", versions, versions["benchmark_version"], m["participant_id"])
                            create_orders(con, aid, weights[aid], day + "T00:00:00+09:00", day, versions["benchmark_version"], m["participant_id"], kind="HISTORICAL_REPLAY", baseline={})
                        execute_pending(con, aid, day, source["config"]["costs"]["trading_cost_bps"], versions["benchmark_version"], m["participant_id"])
                        result = valuate(con, aid, day, versions, run["initial_capital_krw"], stale_days=4)
                        if result["status"] != "OK":
                            raise ValueError("REPLAY_VALUATION_INCOMPLETE")
            if replay.verify_completed(con, run) != 15 or con.execute("SELECT 1 FROM orders WHERE status='pending'").fetchone():
                raise ValueError("REPLAY_NOT_COMPLETE")
        replay.save_state(con, "replay_status", "COMPLETE")
        openings = {}
        for m in source["members"]:
            for aid in m["account_ids"]:
                nav = dict(con.execute("SELECT * FROM nav_daily WHERE account_id=? AND date=?", (aid, days[-1])).fetchone())
                positions = [dict(r) for r in con.execute("SELECT asset_id,quantity,price,market_value,weight FROM holdings_daily WHERE account_id=? AND date=? ORDER BY asset_id", (aid, days[-1]))]
                from src.forward.prices import price_on_or_before
                for position in positions:
                    position["price_date"] = price_on_or_before(con, position["asset_id"], days[-1])[1]
                openings[aid] = dict(kind="REPLAY_FORWARD_OPENING", run_id=fingerprint, forward_start=source["forward_start"],
                    as_of=days[-1], nav=nav["nav"], cash_balance=nav["cash_balance"], holdings=positions, decision_id=m["decision_id"],
                    historical_start=source["start"], historical_end=source["end"])
        series = {aid: [dict(r) for r in con.execute("SELECT date,nav,nav_base100,cumulative_return FROM nav_daily WHERE account_id=? ORDER BY date", (aid,))] for aid in openings}
    archives = []
    engine = create_engine(f"sqlite:///{directory / 'replay_ledger.db'}")
    with Session(engine) as session:
        for m in source["members"]:
            aid = m["personal_account_id"]
            core_id = next(a for a in m["account_ids"] if a != aid)
            pn, cn = series[aid], series[core_id]
            saved_ledger = ledger(session, m["participant_id"])
            saved_ledger["replay_context"] = None
            report = dict(kind="HISTORICAL_REPLAY", run_id=fingerprint, source_sha256=fingerprint,
                start=first, end=days[-1], requested_start=source["start"], requested_end=source["end"],
                decision_id=m["decision_id"], decision_confirmed_at=decisions[m["decision_id"]]["confirmed_at"],
                decision_effective_date=m["effective_date"], initial_capital_krw=run["initial_capital_krw"],
                cost_bps=source["config"]["costs"]["trading_cost_bps"], selection_basis="CURRENT_CONFIRMED_CONFIGURATION",
                execution_basis="INITIAL_BUY_AND_HOLD", valuation_basis="LAST_OBSERVED_CLOSE_MAX_4_CALENDAR_DAYS",
                series=[dict(date=p["date"], personal_nav=p["nav"], core_nav=c["nav"], personal_index=p["nav_base100"], core_index=c["nav_base100"]) for p, c in zip(pn, cn)],
                price_dates={s["date"]: {p["asset_id"]: p["price_date"] for p in s["holdings"]} for s in saved_ledger["snapshots"]},
                weights=weights[aid], core_weights=source["core"], ledger=saved_ledger,
                summary=dict(personal_return=pn[-1]["cumulative_return"], core_return=cn[-1]["cumulative_return"], observations=len(days)))
            archives.append(dict(account_id=aid, participant_id=m["participant_id"], report=report))
    engine.dispose()
    plan = dict(source=source, source_hash=fingerprint, openings=openings, archives=archives)
    validate_plan(plan)
    Path(output_path).write_text(json.dumps(plan, sort_keys=True, allow_nan=False))


def build_plan(source):
    with tempfile.TemporaryDirectory(prefix="robo-handoff-") as temp:
        directory = Path(temp)
        (directory / "input.json").write_text(json.dumps(source))
        env = {**os.environ, "APP_PROFILE": "local", "CAPSTONE_DEMO": "1", "DATABASE_BACKEND": "sqlite",
               "CAPSTONE_DATA_DIR": temp, "DATABASE_URL": "", "CAPSTONE_DESIGN_DATABASE_URL": "", "COMPETITION_REPLAY_DIR": temp}
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--replay-local", str(directory / "input.json"), str(directory / "output.json")],
                       env=env, cwd=ROOT, check=True, capture_output=True, text=True)
        return json.loads((directory / "output.json").read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-10-01")
    parser.add_argument("--end", default="2026-10-24")
    parser.add_argument("--forward-start", default="2026-10-26")
    parser.add_argument("--apply-hash")
    parser.add_argument("--replay-local", nargs=2)
    args = parser.parse_args()
    if args.replay_local:
        replay_local(*args.replay_local)
        return
    from src.forward.db import connect
    from src.forward.runtime import get_database_path
    with closing(connect(get_database_path())) as con:
        # Plan source reads are database-enforced read-only on PostgreSQL.
        if hasattr(con, "_con"):
            con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            if con.execute("SELECT current_database() AS name").fetchone()["name"] != "robo_design":
                raise ValueError("UNEXPECTED_DATABASE")
        else:
            con.execute("PRAGMA query_only=ON")
        receipt = con.execute("SELECT payload_json FROM events WHERE event_type='REPLAY_HANDOFF_APPLIED'").fetchone()
        if receipt:
            value = json.loads(receipt["payload_json"])
            if args.apply_hash and value["plan_hash"] != args.apply_hash:
                raise ValueError("DIFFERENT_HANDOFF_ALREADY_APPLIED")
            print(json.dumps({**value, **audit(con, value), "reused": True}))
            return
        source = snapshot(con, args.start, args.end, args.forward_start)
        con.rollback()
        plan = build_plan(source)
        plan_hash = digest(plan)
        result = dict(status="PLAN", plan_hash=plan_hash, participants=len(source["members"]),
            accounts=len(plan["openings"]), pending_to_cancel=len(source["pending"]),
            requested_start=args.start, requested_end=args.end, forward_start=args.forward_start,
            first_valuation=plan["archives"][0]["report"]["start"], last_valuation=plan["archives"][0]["report"]["end"],
            observations=len(plan["archives"][0]["report"]["series"]), live_nav_created=0)
        if args.apply_hash:
            if not hasattr(con, "_con"):
                con.execute("PRAGMA query_only=OFF")
            receipt = apply(con, plan, args.apply_hash)
            result = {**result, **receipt, **audit(con, receipt), "status": "APPLIED"}
        print(json.dumps(result))


if __name__ == "__main__":
    main()
