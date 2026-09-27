"""Monthly run: risk refresh + core rebalance (core, personal core leg, shadows)."""
from __future__ import annotations

import argparse
import json
import sys
from calendar import monthrange
from datetime import date
from pathlib import Path

import numpy as np

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
from src.forward.run_daily import rebuild_cov
from src.forward.run_weekly import batch_views
from src.forward.views import next_weekday


def main(argv=None) -> int:
    print_banner()
    ap = argparse.ArgumentParser(prog="run_monthly")
    ap.add_argument("--month", default=None, help="YYYY-MM")
    ap.add_argument("--risk-only", action="store_true",
                    help="refresh risk model only, no rebalance orders")
    from src.forward.job_cli import add_job_args, enter_job, finish_job, job_context
    add_job_args(ap)
    args = ap.parse_args(argv)
    cfg = load_forward_config()
    from src.forward.runtime import get_database_path as _dbp
    db_path = _dbp()
    con = connect(db_path)
    if args.month:
        y, m = args.month.split("-")
    else:
        t = date.today()
        y, m = (t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)
        y, m = str(y), f"{m:02d}"
    asof = f"{y}-{m}-{monthrange(int(y), int(m))[1]:02d}"
    ctx = job_context(args, asof)
    job_id, decision = enter_job(db_path, "monthly", ctx)
    if decision == "dry":
        code = _dry_run_monthly(con, cfg, y, m, asof, args.risk_only)
        return finish_job(db_path, None, decision, code, {"dry_run": True}, ctx)
    if decision != "run":
        print(f"monthly job {decision} for {ctx['scheduled_for']}; nothing to do.")
        return finish_job(db_path, None, decision, 0, {}, ctx)
    try:
        code, stats = _execute_monthly(con, cfg, y, m, asof, args.risk_only)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        return finish_job(db_path, job_id, decision, 1, {}, ctx, error=str(e))
    return finish_job(db_path, job_id, decision, code, stats, ctx)


def _dry_run_monthly(con, cfg, y, m, asof, risk_only) -> int:
    n_core = con.execute("SELECT COUNT(*) c FROM accounts WHERE account_type IN ('core','shadow')"
                         " AND status='active'").fetchone()["c"]
    n_pers = con.execute("SELECT COUNT(*) c FROM accounts WHERE account_type='personal'"
                         " AND status='active'").fetchone()["c"]
    npx = con.execute("SELECT COUNT(*) c FROM prices_daily WHERE date <= ?",
                      (asof,)).fetchone()["c"]
    print(f"DRY RUN monthly for {y}-{m} (asof {asof}, risk_only={risk_only}): "
          f"{npx} price rows available, {n_core} core/shadow + {n_pers} personal accounts "
          f"would refresh risk{'' if risk_only else ' and rebalance'}.")
    return 0


def _execute_monthly(con, cfg, y, m, asof, risk_only):
    ft = cfg["forward_test"]
    from src.forward.frozen import load_frozen_benchmark as _lf
    from src.forward.accounts import versions_from_cfg as _vv
    from src.forward.config import resolve as _rs
    frozen_w, _ = _lf(_rs(cfg["frozen_dir"]))
    versions = _vv(cfg)
    first_next = f"{y}-{m}-01"
    from datetime import timedelta as _td
    prev_day = (date.fromisoformat(first_next) - _td(days=1)).isoformat()
    effective = next_weekday(prev_day)

    cov, info = rebuild_cov(con, cfg, asof)
    import numpy as _np
    p = _rs("outputs/forward/latest/risk_cov.npz")
    p.parent.mkdir(parents=True, exist_ok=True)
    _np.savez(str(p), cov=cov.to_numpy(), assets=_np.array(list(cov.columns)),
              asof=_np.array(asof))
    con.execute("INSERT OR REPLACE INTO model_versions (version_id, version_type, version,"
                " created_at, payload_json) VALUES ('MV-RISK', 'risk_model', ?, datetime('now'), ?)",
                (f"RISK_5Y_LW_{asof}", json.dumps(info)))
    log_event(con, "RISK_MODEL_REFRESHED", ft["benchmark_version"], payload=info)
    if risk_only:
        con.commit()
        print(f"month {y}-{m}: risk refreshed asof {asof} (no rebalance orders)")
        print("STATUS: PASS")
        return 0, {"asof": asof, "risk_only": True, "status": "PASS"}
    from src.forward.state import live_orders_blocked
    blocked, reason = live_orders_blocked(con)
    if blocked:
        con.commit()
        print(f"ERROR:\nMonthly rebalance refused: {reason}.")
        return 2, {"status": "REFUSED"}
    n = 0
    # 리밸런싱 밴드: 목표 대비 편차가 밴드 안이면 주문을 만들지 않는다.
    band = (ft.get("core_rebalance") or {}).get("band") or None
    if band:
        print(f"rebalance band: {band}")
    # core + shadow static legs (drift-correcting vs current holdings)
    from src.forward.execution import current_weights as _cw
    for r in con.execute("SELECT * FROM accounts WHERE account_type IN ('core','shadow')"
                         " AND status='active'").fetchall():
        if r["account_type"] == "core":
            w = dict(frozen_w)
        elif r["shadow_name"] == "core_v03":
            w = dict(frozen_w)
        elif r["shadow_name"] == "neutral_60_40":
            import pandas as pd
            w = pd.read_csv(resolve(cfg["phase16_outputs"]) / "neutral_60_40_weights.csv",
                            index_col=0)["weight"].to_dict()
            w = {k: float(v) for k, v in w.items()}
        else:  # equal_weight
            from src.forward.prices import CORE_IDS
            w = {a: 1 / 9 for a in CORE_IDS}
            w["cash"] = 0.0
        record_target(con, r["account_id"], w, effective, "core", versions,
                      ft["benchmark_version"], r["participant_id"])
        n += len(place_target_orders(con, r["account_id"], w, f"{asof}T23:59:59+00:00",
                                     effective, ft["benchmark_version"],
                                     r["participant_id"], kind="CORE_REBALANCE",
                                     baseline=_cw(con, r["account_id"], asof),
                                     band=band))
    # personal accounts: fresh core + current views
    for p_ in list_participants(con, "active"):
        pid = p_["participant_id"]
        acc = con.execute("SELECT account_id FROM accounts WHERE participant_id = ?"
                          " AND account_type='personal'", (pid,)).fetchone()
        if acc is None:
            continue
        tids = sorted({theme_asset_id(v["theme_id"])
                       for v in batch_views(con, pid, "9999-99-99", effective)})
        res = build_personalized(frozen_w, tids, cfg, cov)
        import json as _json
        prev = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id = ?"
                           " AND effective_date < ? ORDER BY effective_date DESC LIMIT 1",
                           (acc["account_id"], effective)).fetchone()
        prev_w = _json.loads(prev["weights_json"]) if prev else {}
        record_target(con, acc["account_id"], res["weights"], effective, "personal",
                      versions, ft["benchmark_version"], pid)
        n += len(place_target_orders(con, acc["account_id"], res["weights"],
                                     f"{asof}T23:59:59+00:00", effective,
                                     ft["benchmark_version"], pid, kind="CORE_REBALANCE",
                                     baseline=prev_w, band=band))
    con.commit()
    print(f"month {y}-{m}: risk refreshed asof {asof}, {n} rebalance orders, effective {effective}")
    print("STATUS: PASS")
    return 0, {"asof": asof, "orders": n, "effective": effective, "status": "PASS"}


if __name__ == "__main__":
    raise SystemExit(main())
