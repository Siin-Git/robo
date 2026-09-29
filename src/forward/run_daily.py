"""Daily run: refresh prices, execute pending orders, value holdings, guardrails."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.forward.accounts import versions_from_cfg
from src.forward.config import load_forward_config, resolve
from src.forward.db import connect
from src.forward.runtime import get_database_path, print_banner
from src.forward.execution import execute_pending
from src.forward.frozen import load_frozen_benchmark
from src.forward.ledger import nav_series, valuate
from src.forward.portfolio import build_personalized
from src.forward.prices import price_series
from src.forward.risk import build_cov_asof


def tickers_map(con, frozen_meta) -> dict:
    m = dict(frozen_meta.get("tickers", {}))
    out = {}
    for aid, t in m.items():
        if aid == "FX_USDKRW":
            out["__FX__"] = t
        else:
            out[aid] = t
    for r in con.execute("SELECT theme_id, ticker FROM themes WHERE active").fetchall():
        from src.forward.prices import theme_asset_id
        out[theme_asset_id(r["theme_id"])] = r["ticker"]
    return out


def latch_first_execution(con, model_version: str) -> str | None:
    """Record global first execution once from the trade ledger. Never overwrites."""
    from src.forward.state import get_state as _gs, set_state_once as _ss
    from src.forward.db import log_event as _le
    if _gs(con, "first_execution_at") is None:
        gfirst = con.execute("SELECT MIN(execution_at) m FROM trades").fetchone()["m"]
        if gfirst is not None:
            _ss(con, "first_execution_at", gfirst)
            _le(con, "FIRST_EXECUTION_RECORDED", model_version,
                payload={"first_execution_at": gfirst})
            con.commit()
            return gfirst
    return _gs(con, "first_execution_at")


def cov_cache_path(cfg) -> Path:
    return resolve("outputs/forward/latest/risk_cov.npz")


def load_or_build_cov(con, cfg, asof: str, persist: bool = True):
    import numpy as _np
    p = cov_cache_path(cfg)
    if p.exists():
        z = _np.load(str(p), allow_pickle=True)
        cov = pd.DataFrame(z["cov"], index=list(z["assets"]), columns=list(z["assets"]))
        return cov, {"cached": True, "asof": str(z["asof"])}
    cov, info = rebuild_cov(con, cfg, asof)
    if persist:
        import numpy as _np2
        _np2.savez(str(p), cov=cov.to_numpy(), assets=_np2.array(list(cov.columns)),
                   asof=_np2.array(asof))
    info["cached"] = False
    return cov, info


def rebuild_cov(con, cfg, asof: str):
    from src.forward.prices import CORE_IDS, theme_asset_id
    themes = [r["theme_id"] for r in con.execute(
        "SELECT theme_id FROM themes WHERE active").fetchall()]
    assets = list(CORE_IDS) + [theme_asset_id(t) for t in themes]
    have = {r["asset_id"] for r in con.execute("SELECT DISTINCT asset_id FROM prices_daily").fetchall()}
    assets = [a for a in assets if a in have]
    return build_cov_asof(con, assets, asof, 5, 52)


def main(argv=None) -> int:
    print_banner()
    import argparse
    from src.forward.job_cli import add_job_args, enter_job, finish_job, job_context
    from src.forward.runtime import get_database_path as _dbp
    ap = argparse.ArgumentParser(prog="run_daily")
    add_job_args(ap)
    ap.add_argument("--force", action="store_true",
                    help="장중이어도 실행한다(잠정가가 종가로 저장될 수 있다)")
    args = ap.parse_args(argv)
    # 장중에는 수집하지 않는다. 가격을 받은 뒤 거르는 것이 아니라 시작을 막는다.
    # dry-run 은 가격을 받지 않으므로 언제든 허용한다.
    if not args.force and not args.dry_run:
        from src.forward.market_hours import guard_message
        msg = guard_message()
        if msg:
            print("ERROR:\n" + msg)
            return 2
    cfg = load_forward_config()
    db_path = _dbp()
    con = connect(db_path)
    today = date.today().isoformat()
    ctx = job_context(args, today)
    job_id, decision = enter_job(db_path, "daily", ctx)
    if decision == "dry":
        code = _dry_run_daily(con, cfg, today)
        return finish_job(db_path, None, decision, code, {"dry_run": True}, ctx)
    if decision != "run":
        print(f"daily job {decision} for {ctx['scheduled_for']}; nothing to do.")
        return finish_job(db_path, None, decision, 0, {}, ctx)
    try:
        code, stats = _execute_daily(con, cfg, today)
    except Exception as e:  # noqa: BLE001 - must record failure loudly
        import traceback
        traceback.print_exc()
        return finish_job(db_path, job_id, decision, 1, {}, ctx, error=str(e))
    return finish_job(db_path, job_id, decision, code, stats, ctx)


def stale_assets(con, asof: str, stale_days: int) -> list[str]:
    """마지막 가격이 stale_days 를 넘긴 자산.

    "오늘 종가가 아직 없다"(휴장·마감 전)와 "가격이 실제로 밀렸다"를 구분한다.
    전자는 매일 정상적으로 발생하므로 알림으로 내보내면 안 된다.
    """
    from datetime import date as _date, timedelta as _td
    cutoff = (_date.fromisoformat(asof[:10]) - _td(days=int(stale_days))).isoformat()
    return sorted(r["asset_id"] for r in con.execute(
        "SELECT asset_id, MAX(date) m FROM prices_daily GROUP BY asset_id").fetchall()
        if r["m"] is not None and r["m"] < cutoff)


def refresh_payload(con, rep: dict, stale_days: int) -> dict:
    """가격 수집 결과를 events 에 남길 형태로 정리한다.

    fetch_failed 는 조회가 예외로 끝난 자산이다. 조회 구간에 거래일이 하나도
    없으면(추석 연휴 등) 야후가 빈 시리즈를 주고 예외가 나므로, 이것만으로는
    장애인지 휴장인지 알 수 없다. 실제로 문제가 되는 것은 stale_assets 다.
    """
    asof = rep.get("asof") or ""
    return {"asof": asof,
            "new_points": int(rep.get("new_points") or 0),
            "fetch_failed": sorted(rep.get("stale") or []),
            "stale_assets": stale_assets(con, asof, stale_days) if asof else [],
            "stale_price_days": int(stale_days)}


def _dry_run_daily(con, cfg, today) -> int:
    """Read-only plan: zero writes, zero job records."""
    ft = cfg["forward_test"]
    n_assets = con.execute("SELECT COUNT(DISTINCT asset_id) c FROM prices_daily").fetchone()["c"]
    stale_assets = [r["asset_id"] for r in con.execute(
        "SELECT asset_id, MAX(date) m FROM prices_daily GROUP BY asset_id").fetchall()
        if r["m"] < today]
    pend = con.execute("SELECT COUNT(*) c FROM orders WHERE status='pending'").fetchone()["c"]
    n_acct = con.execute("SELECT COUNT(*) c FROM accounts WHERE status='active'").fetchone()["c"]
    print(f"DRY RUN daily for {today}: {n_assets} priced assets "
          f"({len(stale_assets)} stale: {stale_assets[:5]}), "
          f"{pend} pending orders, {n_acct} active accounts would be valuated.")
    print("would update prices, would execute N orders, would value N accounts.")
    return 0


def _execute_daily(con, cfg, today):
    from src.forward.prices import refresh_live
    ft = cfg["forward_test"]
    frozen_w, frozen_meta = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
    versions = versions_from_cfg(cfg)

    from src.forward.db import log_event as _log_event
    stale_days = int(ft.get("stale_price_days", 14))
    try:
        rep = refresh_live(con, tickers_map(con, frozen_meta))
    except Exception as exc:  # noqa: BLE001 - 수집 실패는 반드시 기록한다
        _log_event(con, "PRICE_REFRESH_FAILED", ft["benchmark_version"],
                   payload={"error": str(exc)[:500], "asof": today})
        con.commit()
        raise
    print(f"refresh: {rep}")
    asof = rep["asof"]
    price_report = refresh_payload(con, rep, stale_days)
    _log_event(con, "PRICE_REFRESH", ft["benchmark_version"], payload=price_report)
    con.commit()
    if price_report["stale_assets"]:
        print(f"WARNING: stale prices ({stale_days}d+): {price_report['stale_assets']}")

    accounts = [dict(r) for r in con.execute("SELECT * FROM accounts WHERE status='active'").fetchall()]
    # Initial orders for accounts that hold targets but never traded: submitted
    # now, effective today -> first execution at then-available prices (never retroactive).
    # Blocked entirely while live pre-launch (inception NULL).
    from src.forward.db import log_event, now_iso
    from src.forward.state import get_state as _get_state, live_orders_blocked, set_state_once
    import json as _json
    blocked, blocked_reason = live_orders_blocked(con)
    if blocked:
        print(f"order creation blocked: {blocked_reason}")
    else:
        for a in accounts:
            n_orders = con.execute("SELECT COUNT(*) c FROM orders WHERE account_id = ?",
                                   (a["account_id"],)).fetchone()["c"]
            if n_orders:
                continue
            t = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id = ?"
                            " ORDER BY effective_date DESC, created_at DESC, target_id DESC LIMIT 1", (a["account_id"],)).fetchone()
            if not t:
                continue
            from src.forward.execution import create_orders as _co
            _co(con, a["account_id"], _json.loads(t["weights_json"]), now_iso(), today,
                ft["benchmark_version"], a["participant_id"], kind="INITIAL_BENCHMARK_ORDER")
            log_event(con, "INITIAL_BENCHMARK_ORDER_CREATED", ft["benchmark_version"],
                      a["participant_id"], a["account_id"], {"effective": today})
    con.commit()
    for a in accounts:
        execute_pending(con, a["account_id"], asof,
                        float(ft["costs"]["trading_cost_bps"]), ft["benchmark_version"],
                        a["participant_id"])
        first = con.execute("SELECT MIN(execution_at) m FROM trades WHERE account_id = ?",
                            (a["account_id"],)).fetchone()["m"]
        if first == asof:
            from src.forward.db import log_event as _le
            _le(con, "INITIAL_BENCHMARK_EXECUTED", ft["benchmark_version"],
                a["participant_id"], a["account_id"], {"first_execution_date": first})
    # latch global first execution once (never overwritten)
    latch_first_execution(con, ft["benchmark_version"])
    con.commit()
    maxdate = con.execute("SELECT MAX(date) m FROM prices_daily").fetchone()["m"]
    results = {}
    for a in accounts:
        r = valuate(con, a["account_id"], maxdate, versions,
                    float(a["initial_capital_krw"]), int(ft.get("stale_price_days", 14)))
        results[a["account_id"]] = r
    con.commit()

    # ---- guardrails ----
    fails, partials = [], []
    for aid, r in results.items():
        if r["status"] == "NAV_INCOMPLETE" and r.get("reason") == "no executions yet":
            partials.append(f"{aid}: awaiting first execution (no NAV yet)")
        elif r["status"] == "NAV_INCOMPLETE":
            fails.append(f"{aid}: {r.get('reason', r.get('missing', 'nav incomplete'))}")
        elif r["status"] == "STALE_PRICE":
            partials.append(f"{aid}: stale price")
    pend = con.execute("SELECT COUNT(*) c FROM orders WHERE status='pending'").fetchone()["c"]
    if pend:
        no_price = []
        for r in con.execute("SELECT DISTINCT asset_id FROM orders WHERE status='pending'").fetchall():
            mx = con.execute("SELECT MAX(date) m FROM prices_daily WHERE asset_id = ?",
                             (r["asset_id"],)).fetchone()["m"]
            if mx is None:
                no_price.append(r["asset_id"])
        if no_price:
            partials.append(f"execution price missing for {no_price}")
    # holdings weight sums
    for a in accounts:
        h = con.execute("SELECT date, SUM(weight) s FROM holdings_daily WHERE account_id = ?"
                        " GROUP BY date ORDER BY date DESC LIMIT 1", (a["account_id"],)).fetchone()
        n = con.execute("SELECT nav, cash_balance FROM nav_daily WHERE account_id = ?"
                        " ORDER BY date DESC LIMIT 1", (a["account_id"],)).fetchone()
        if h and n and abs((h["s"] + n["cash_balance"] / n["nav"]) - 1.0) > 1e-6:
            fails.append(f"{a['account_id']}: holdings accounting mismatch")
    # active sleeve + guardrail on latest personal targets
    try:
        cov, _ = load_or_build_cov(con, cfg, maxdate)
        for a in accounts:
            if a["account_type"] != "personal":
                continue
            t = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id = ?"
                            " ORDER BY effective_date DESC, created_at DESC, target_id DESC LIMIT 1", (a["account_id"],)).fetchone()
            if not t:
                continue
            import json
            w = json.loads(t["weights_json"])
            th = sum(v for k, v in w.items() if k.startswith("theme:"))
            if th > float(ft["active_sleeve"]["max_total_weight"]) + 1e-9:
                fails.append(f"{a['account_id']}: active sleeve {th:.3f} exceeds max")
    except Exception as e:
        partials.append(f"risk check unavailable: {e}")

    print(f"valuated {len(results)} accounts at {maxdate}; pending orders: {pend}")
    stats = {"asof": maxdate, "valuated": len(results), "pending": pend,
             "new_points": price_report["new_points"],
             "fetch_failed": price_report["fetch_failed"],
             "stale_assets": price_report["stale_assets"]}
    if fails:
        print("FAIL:")
        for f in fails:
            print(f"  - {f}")
        print("STATUS: FAIL")
        stats["status"] = "FAIL"
        return 1, stats
    if partials:
        print("PARTIAL:")
        for p in partials:
            print(f"  - {p}")
        print("STATUS: PARTIAL")
        stats["status"] = "PARTIAL"
        return 0, stats
    print("STATUS: PASS")
    stats["status"] = "PASS"
    return 0, stats


if __name__ == "__main__":
    raise SystemExit(main())
