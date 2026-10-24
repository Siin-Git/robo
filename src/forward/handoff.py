"""Reviewed, atomic replay-to-forward opening; no historical live trades/NAV."""
from datetime import date
from hashlib import sha256
import json
import math

from . import competition as gate
from .config import load_forward_config, resolve
from .frozen import load_frozen_benchmark
from .db import log_event, now_iso
from .opening import EVENT, opening


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def snapshot(con, start, end, forward_start):
    if not date.fromisoformat(start) <= date.fromisoformat(end) < date.fromisoformat(forward_start):
        raise ValueError("INVALID_REPLAY_WINDOW")
    if date.fromisoformat(end) > gate.now_kst().date():
        raise ValueError("REPLAY_END_IN_FUTURE")
    if gate.saved_start(con):
        raise ValueError("START_ALREADY_SCHEDULED")
    cohort = gate.read_cohort()
    members, count, ready = gate.readiness(con, cohort) if cohort else ([], 0, False)
    if not ready or count != 15:
        raise ValueError("ALL_15_PARTICIPANTS_REQUIRED")
    members = sorted(members, key=lambda m: m["user_id"])
    accounts, decisions, participants, pending = [], [], [], []
    for member in members:
        participants.append(dict(con.execute("SELECT * FROM participants WHERE participant_id=?", (member["participant_id"],)).fetchone()))
        decision = dict(con.execute("SELECT * FROM portfolio_decisions WHERE decision_id=?", (member["decision_id"],)).fetchone())
        decisions.append(decision)
        for aid in sorted(member["account_ids"]):
            if opening(con, aid):
                raise ValueError("OPENING_ALREADY_EXISTS")
            for table in ("trades", "holdings_daily", "nav_daily"):
                if con.execute(f"SELECT 1 FROM {table} WHERE account_id=? LIMIT 1", (aid,)).fetchone():
                    raise ValueError("EXISTING_OPERATING_HISTORY")
            accounts.append(dict(con.execute("SELECT * FROM accounts WHERE account_id=?", (aid,)).fetchone()))
            pending.extend(dict(r) for r in con.execute("SELECT * FROM orders WHERE account_id=? AND status='pending' ORDER BY order_id", (aid,)))
    cfg = load_forward_config()
    core, _ = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
    assets = set(a for a, w in core.items() if w > 0 and a != "cash")
    for d in decisions:
        for key in ("weights_json", "provenance_json"):
            if isinstance(d.get(key), str):
                d[key] = json.loads(d[key])
        assets.update(a for a, w in d["weights_json"].items() if w > 0 and a != "cash")
    prices = [dict(r) for r in con.execute("SELECT * FROM prices_daily WHERE date>=? AND date<=? ORDER BY date,asset_id", (start, end)) if r["asset_id"] in assets]
    if any(not p["source"] or any(t in p["source"].lower() for t in ("synthetic", "fixture", "replay", "mock"))
           or not math.isfinite(float(p["price"])) or float(p["price"]) <= 0 for p in prices):
        raise ValueError("UNVERIFIED_PRICE_SOURCE")
    if {p["asset_id"] for p in prices} != assets:
        raise ValueError("REPLAY_PRICES_MISSING")
    capitals = {float(a["initial_capital_krw"]) for a in accounts}
    if len(capitals) != 1 or next(iter(capitals)) <= 0:
        raise ValueError("INITIAL_CAPITAL_MISMATCH")
    return dict(start=start, end=end, forward_start=forward_start, cohort=cohort, members=members,
                accounts=accounts, decisions=decisions, participants=participants, pending=pending,
                prices=prices, core=core, config=cfg["forward_test"])


def validate_plan(plan):
    source = plan["source"]
    if digest(source) != plan["source_hash"]:
        raise ValueError("SOURCE_HASH_MISMATCH")
    aids = {a["account_id"] for a in source["accounts"]}
    if len(aids) != 30 or set(plan["openings"]) != aids or len(plan["archives"]) != 15:
        raise ValueError("INCOMPLETE_HANDOFF")
    for aid, value in plan["openings"].items():
        if value["forward_start"] != source["forward_start"] or value["run_id"] != plan["source_hash"]:
            raise ValueError("OPENING_LINEAGE_MISMATCH")
        if not source["start"] <= value["as_of"] <= source["end"]:
            raise ValueError("OPENING_DATE_MISMATCH")
        holdings = value["holdings"]
        numbers = [value["nav"], value["cash_balance"], *[p[k] for p in holdings for k in ("quantity", "price", "market_value")]]
        if any(not math.isfinite(float(v)) for v in numbers) or value["nav"] <= 0 or value["cash_balance"] < -1e-5:
            raise ValueError("INVALID_OPENING_AMOUNT")
        if len({p["asset_id"] for p in holdings}) != len(holdings) or any(p["quantity"] < 0 or p["price"] <= 0 for p in holdings):
            raise ValueError("INVALID_OPENING_POSITION")
        if any(abs(p["quantity"] * p["price"] - p["market_value"]) > 1e-5 for p in holdings):
            raise ValueError("POSITION_IDENTITY_FAILED")
        if abs(sum(p["market_value"] for p in holdings) + value["cash_balance"] - value["nav"]) > 1e-5:
            raise ValueError("OPENING_IDENTITY_FAILED")
    for archive in plan["archives"]:
        aid = archive["account_id"]
        if archive["report"]["run_id"] != plan["source_hash"] or archive["report"]["series"][-1]["personal_nav"] != plan["openings"][aid]["nav"]:
            raise ValueError("ARCHIVE_OPENING_MISMATCH")


def apply(con, plan, expected_hash):
    """Caller owns the connection. Lock/revalidate before one all-or-nothing commit."""
    if digest(plan) != expected_hash:
        raise ValueError("PLAN_HASH_MISMATCH")
    validate_plan(plan)
    from .run_daily import _DeferredCommitConnection
    con.rollback()
    try:
        if hasattr(con, "_con"):
            con.execute("SET LOCAL lock_timeout = '15s'")
            con.execute("LOCK TABLE accounts,portfolio_decisions,orders,trades,nav_daily,holdings_daily,forward_state,events IN SHARE ROW EXCLUSIVE MODE")
        else:
            con.execute("BEGIN IMMEDIATE")
        receipt = con.execute("SELECT payload_json FROM events WHERE event_type='REPLAY_HANDOFF_APPLIED'").fetchone()
        if receipt:
            receipt = json.loads(receipt["payload_json"])
            if receipt["plan_hash"] != expected_hash:
                raise ValueError("DIFFERENT_HANDOFF_ALREADY_APPLIED")
            if any(not opening(con, aid) or opening(con, aid)["run_id"] != plan["source_hash"] for aid in plan["openings"]):
                raise ValueError("APPLIED_HANDOFF_INCOMPLETE")
            con.rollback()
            return {**receipt, "reused": True}
        source = plan["source"]
        current = snapshot(con, source["start"], source["end"], source["forward_start"])
        if digest(current) != plan["source_hash"]:
            raise ValueError("SOURCE_CHANGED_REPLAN_REQUIRED")
        tx = _DeferredCommitConnection(con)
        version = source["config"]["benchmark_version"]
        stamp = now_iso()
        for order in source["pending"]:
            con.execute("UPDATE orders SET status='cancelled' WHERE order_id=? AND status='pending'", (order["order_id"],))
            log_event(con, "ORDER_CANCELLED_FOR_HANDOFF", version, None, order["account_id"],
                      {"order_id": order["order_id"], "run_id": plan["source_hash"], "reason": "REPLACED_BY_INHERITED_POSITIONS"})
        scheduled = gate.schedule_start(tx, source["forward_start"])
        expected_members = {(m["user_id"], m["decision_id"]) for m in source["members"]}
        if {(m["user_id"], m["decision_id"]) for m in scheduled["members"]} != expected_members:
            raise ValueError("ROSTER_CHANGED_REPLAN_REQUIRED")
        for archive in plan["archives"]:
            log_event(con, "HISTORICAL_REPLAY_ARCHIVED", version, archive["participant_id"], archive["account_id"],
                      {**archive["report"], "generated_at": stamp, "ledger_archived_at": stamp})
        for member in source["members"]:
            for aid in member["account_ids"]:
                log_event(con, EVENT, version, member["participant_id"], aid, plan["openings"][aid])
            log_event(con, "DECISION_ORDER:" + member["decision_id"], version, member["participant_id"], member["personal_account_id"],
                      {"decision_id": member["decision_id"], "run_id": plan["source_hash"], "execution_kind": "INHERITED_REPLAY_POSITION"})
        receipt = dict(plan_hash=expected_hash, run_id=plan["source_hash"], forward_start=source["forward_start"],
                       openings=len(plan["openings"]), archives=len(plan["archives"]), cancelled_pending=len(source["pending"]))
        log_event(con, "REPLAY_HANDOFF_APPLIED", version, None, None, receipt)
        con.commit()
        return {**receipt, "reused": False}
    except BaseException:
        con.rollback()
        raise
