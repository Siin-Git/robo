"""Weekly run: cutoff batching, personalized targets, active rebalance orders."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.forward.accounts import place_target_orders, record_target, versions_from_cfg
from src.forward.config import load_forward_config, resolve
from src.forward.db import connect, log_event
from src.forward.runtime import get_database_path, print_banner
from src.forward.frozen import load_frozen_benchmark
from src.forward.participants import list_participants
from src.forward.portfolio import build_personalized
from src.forward.prices import theme_asset_id
from src.forward.run_daily import load_or_build_cov
from src.forward.views import active_views, mark_held


def batch_views(con, participant_id: str, cycle_week: str, batch_effective: str) -> list[dict]:
    """Views of this cycle applicable at the batch effective date.

    Canonical filter: COALESCE(cycle_date, cycle_week) so legacy rows without
    cycle_date still resolve. Effective dates are read from DB, never recomputed.
    """
    out = []
    for v in active_views(con, participant_id):
        cyc = v.get("cycle_date") or v["cycle_week"]
        if cyc > cycle_week:
            continue
        if v["effective_at"] > batch_effective:
            continue
        if v["end_at"] and v["end_at"][:10] <= batch_effective:
            continue
        out.append(v)
    # one row per theme (latest wins)
    seen: dict[str, dict] = {}
    for v in sorted(out, key=lambda r: r["submitted_at"]):
        seen[v["theme_id"]] = v
    return list(seen.values())


def main(argv=None) -> int:
    print_banner()
    ap = argparse.ArgumentParser(prog="run_weekly")
    ap.add_argument("--week", default=None, help="Friday cycle label YYYY-MM-DD")
    from src.forward.job_cli import add_job_args, enter_job, finish_job, job_context
    add_job_args(ap)
    args = ap.parse_args(argv)
    cfg = load_forward_config()
    from src.forward.runtime import get_database_path as _dbp
    db_path = _dbp()
    con = connect(db_path)
    friday = args.week or _default_friday(con)
    ctx = job_context(args, friday)
    job_id, decision = enter_job(db_path, "weekly", ctx)
    if decision == "dry":
        code = _dry_run_weekly(con, cfg, friday)
        return finish_job(db_path, None, decision, code, {"dry_run": True}, ctx)
    if decision != "run":
        print(f"weekly job {decision} for {ctx['scheduled_for']}; nothing to do.")
        return finish_job(db_path, None, decision, 0, {}, ctx)
    try:
        code, stats = _execute_weekly(con, cfg, friday)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return finish_job(db_path, job_id, decision, 1, {}, ctx, error=str(e))
    return finish_job(db_path, job_id, decision, code, stats, ctx)


def _default_friday(con) -> str:
    row = con.execute("SELECT MAX(date) m FROM prices_daily").fetchone()
    if not row or not row["m"]:
        raise RuntimeError("no prices; run init/daily first")
    from datetime import date as _date, timedelta as _td
    d = _date.fromisoformat(row["m"])
    return (d + _td(days=(4 - d.weekday()))).isoformat()


def _base_for_participant(con, participant_id: str, frozen_w: dict) -> dict:
    """User-selected base if exists, else frozen CORE."""
    try:
        row = con.execute(
            "SELECT weights_json FROM base_portfolio_selections WHERE participant_id = ? AND status='active' ORDER BY selected_at DESC LIMIT 1",
            (participant_id,)).fetchone()
        if row and row[0]:
            import json as _j
            w = _j.loads(row[0]) if isinstance(row[0], str) else row[0]
            return {k: float(v) for k, v in w.items()}
    except Exception:
        pass
    return dict(frozen_w)


def _dry_run_weekly(con, cfg, friday) -> int:
    from src.forward.views import next_weekday
    effective = next_weekday(friday)
    parts = list_participants(con, "active")
    n_views = sum(len(batch_views(con, p["participant_id"], friday, effective)) for p in parts)
    print(f"DRY RUN weekly for cycle {friday} (effective {effective}): "
          f"{len(parts)} active participants, {n_views} applicable views; "
          f"would generate personalized targets + active rebalance orders.")
    return 0


def _execute_weekly(con, cfg, friday):
    ft = cfg["forward_test"]
    from src.forward.frozen import load_frozen_benchmark as _lf
    from src.forward.accounts import versions_from_cfg as _vv
    from src.forward.config import resolve as _rs
    from src.forward.state import live_orders_blocked
    blocked, reason = live_orders_blocked(con)
    if blocked:
        print(f"ERROR:\nWeekly rebalance refused: {reason}.")
        return 2, {"status": "REFUSED"}
    frozen_w, _ = _lf(_rs(cfg["frozen_dir"]))
    versions = _vv(cfg)
    from src.forward.views import next_weekday
    effective = next_weekday(friday)
    cov, _ = load_or_build_cov(con, cfg, friday)
    n_orders = 0
    n_targets = 0
    for p in list_participants(con, "active"):
        pid = p["participant_id"]
        views = batch_views(con, pid, friday, effective)
        submitted_this_cycle = [v for v in active_views(con, pid)
                                if (v.get("cycle_date") or v["cycle_week"]) == friday]
        if not submitted_this_cycle:
            mark_held(con, pid, friday, ft["benchmark_version"])
        tids = sorted({theme_asset_id(v["theme_id"]) for v in views})
        # Base portfolio: prefer user-selected frontier base if exists, else CORE_V0.3
        base_w = _base_for_participant(con, pid, frozen_w)
        res = build_personalized(base_w, tids, cfg, cov)
        acc = con.execute("SELECT account_id FROM accounts WHERE participant_id = ?"
                          " AND account_type='personal'", (pid,)).fetchone()
        if acc is None:
            continue
        import json as _json
        prev = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id = ?"
                           " AND effective_date < ? ORDER BY effective_date DESC LIMIT 1",
                           (acc["account_id"], effective)).fetchone()
        prev_w = _json.loads(prev["weights_json"]) if prev else {}
        record_target(con, acc["account_id"], res["weights"], effective, "personal",
                      versions, ft["benchmark_version"], pid)
        n_targets += 1
        n_orders += len(place_target_orders(
            con, acc["account_id"], res["weights"], f"{friday}T23:59:59+00:00", effective,
            ft["benchmark_version"], pid, kind="ACTIVE_REBALANCE", baseline=prev_w))
        log_event(con, "ACTIVE_REBALANCE", ft["benchmark_version"], pid, acc["account_id"],
                  {"cycle_week": friday, "effective": effective, "te": res["te"],
                   "vol": res["vol"], "scaled": res["scaled"]})
    con.commit()
    print(f"week {friday} -> effective {effective}: {n_orders} active orders")
    print("STATUS: PASS")
    return 0, {"cycle": friday, "effective": effective, "targets": n_targets,
               "orders": n_orders, "status": "PASS"}


if __name__ == "__main__":
    raise SystemExit(main())
