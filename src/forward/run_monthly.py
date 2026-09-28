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
from src.forward.run_weekly import _base_for_participant, batch_views


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
    # 효력일은 결정 기준일(asof, 그 달 말일)의 다음 거래일이다.
    # 예전에는 그 달 1일로 잡혀 제출 시점보다 과거였고, 나중 데이터로 판단해
    # 이전 종가에 체결하는 형태가 됐다(inception 가드가 막아 주문만 쌓였다).
    from src.forward.rebalance_schedule import effective_date as _eff
    effective = _eff(asof)

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
    # 주기 판정: 분기 설정이면 3·6·9·12월 말에만 주문을 만든다.
    # 위험 모형 갱신은 주기와 무관하게 매달 돈다(risk_refresh 는 별도 설정).
    from src.forward.rebalance_schedule import is_rebalance_period, skip_reason
    frequency = (ft.get("core_rebalance") or {}).get("frequency", "monthly")
    if not is_rebalance_period(int(y), int(m), frequency):
        con.commit()
        reason = skip_reason(int(y), int(m), frequency)
        print(f"month {y}-{m}: risk refreshed asof {asof}; no rebalance ({reason})")
        print("STATUS: PASS")
        return 0, {"asof": asof, "orders": 0, "rebalanced": False,
                   "frequency": frequency, "status": "PASS"}
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
        res = build_personalized(_base_for_participant(con, pid, frozen_w), tids, cfg, cov)
        record_target(con, acc["account_id"], res["weights"], effective, "personal",
                      versions, ft["benchmark_version"], pid)
        # 월간 리밸런싱은 실제 보유 비중 기준으로 교정한다(core/shadow 와 동일).
        # 직전 목표 기준이면 가격 변동으로 생긴 드리프트가 누적된 채 남는다.
        # 목표에서 빠진 테마는 create_orders 가 목표 0 으로 매도한다.
        n += len(place_target_orders(con, acc["account_id"], res["weights"],
                                     f"{asof}T23:59:59+00:00", effective,
                                     ft["benchmark_version"], pid, kind="CORE_REBALANCE",
                                     baseline=_cw(con, acc["account_id"], asof),
                                     band=band))
    con.commit()
    print(f"month {y}-{m}: risk refreshed asof {asof}, {n} rebalance orders, effective {effective}")
    print("STATUS: PASS")
    return 0, {"asof": asof, "orders": n, "effective": effective,
               "rebalanced": True, "frequency": frequency, "status": "PASS"}


if __name__ == "__main__":
    raise SystemExit(main())
