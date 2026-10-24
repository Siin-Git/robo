"""Daily run: refresh prices, execute pending orders, value holdings, guardrails."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from contextlib import contextmanager

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
from src.forward.competition import guarded_batch
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
        from .replay import connection_directory
        if connection_directory(con):
            floor = _gs(con, "forward_test_inception_at")
            gfirst = con.execute("SELECT MIN(execution_at) m FROM trades WHERE execution_at>=?",
                                 (floor[:10],)).fetchone()["m"] if floor else None
        else:
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
    ap.add_argument("--use-stored-prices", action="store_true",
                    help="Reuse collected prices; skip refresh_live without changing execution rules")
    args = ap.parse_args(argv)
    # 장중에는 수집하지 않는다. 가격을 받은 뒤 거르는 것이 아니라 시작을 막는다.
    # dry-run and stored-price valuation fetch no prices. Only refresh_live needs
    # the wall-clock guard; completed-session collection has its own per-bar filter.
    if not args.force and not args.dry_run and not args.use_stored_prices:
        from src.forward.market_hours import guard_message
        msg = guard_message()
        if msg:
            print("ERROR:\n" + msg)
            return 2
    cfg = load_forward_config()
    db_path = _dbp()
    con = connect(db_path)
    from src.forward.runtime import kst_today
    today = kst_today().isoformat()
    ctx = job_context(args, today)
    job_id, decision = enter_job(db_path, "daily", ctx)
    if decision == "dry":
        code = _dry_run_daily(con, cfg, today)
        return finish_job(db_path, None, decision, code, {"dry_run": True}, ctx)
    if decision != "run":
        print(f"daily job {decision} for {ctx['scheduled_for']}; nothing to do.")
        return finish_job(db_path, None, decision, 0, {}, ctx)
    try:
        code, stats = _execute_daily(con, cfg, today, use_stored_prices=args.use_stored_prices)
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
    from .competition import policy
    competition = policy(con)
    import json
    print("Competition read-only readiness: " + json.dumps({
        key: competition.get(key) for key in
        ("managed", "status", "reason", "ready", "required", "start_date")}))
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


class _DeferredCommitConnection:
    """Daily account unit of work; existing engine commits belong to the caller.

    Delegates SQL unchanged. Other callers of the financial engines keep their
    existing commit behavior. No savepoints are invalidated by helper commits.
    """
    def __init__(self, con):
        self.connection = con

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        pass


@contextmanager
def _account_transaction(con, account_id):
    # PostgreSQL row lock / SQLite writer lock, held through order marker,
    # execution and valuation because the engine's commits are deferred.
    try:
        con.execute("UPDATE accounts SET status=status WHERE account_id=?", (account_id,))
        tx = _DeferredCommitConnection(con)
        from src.forward.competition import batch_guard
        with batch_guard(tx):
            yield tx
        con.commit()
    except BaseException:
        con.rollback()
        raise


def _create_account_orders(con, a, competition, asof, today, ft):
    """Existing confirmed-decision/CORE order rules, in the account transaction."""
    from src.forward.competition import initial_decision, account_gate
    if account_gate(con, a["account_id"])[0]:
        return
    from src.forward.decision_policy import latest_decision, weights as decision_weights
    from src.forward.db import log_event, now_iso
    import json as _json
    from .opening import opening
    inherited = opening(con, a["account_id"], asof)
    decision = latest_decision(con, a["account_id"])
    if competition["managed"] and not inherited and not con.execute(
            "SELECT 1 FROM trades WHERE account_id=? LIMIT 1", (a["account_id"],)).fetchone():
        decision = initial_decision(con, a["account_id"]) or decision
    if decision:
        if str(decision["effective_date"])[:10] > asof:
            con.commit()
            return
        tag = "DECISION_ORDER:" + decision["decision_id"]
        if con.execute("SELECT event_id FROM events WHERE event_type=? AND account_id=?", (tag, a["account_id"])).fetchone():
            con.commit()
            return
        from src.forward.execution import create_orders, current_weights
        has_trades = con.execute("SELECT trade_id FROM trades WHERE account_id=? LIMIT 1", (a["account_id"],)).fetchone()
        baseline = current_weights(con, a["account_id"], asof) if has_trades or inherited else {}
        create_orders(con, a["account_id"], decision_weights(decision), decision["confirmed_at"], str(decision["effective_date"])[:10],
                      ft["benchmark_version"], a["participant_id"], kind="DECISION", baseline=baseline)
        log_event(con, tag, ft["benchmark_version"], a["participant_id"], a["account_id"], {"decision_id":decision["decision_id"]})
        con.commit()
        return
    n_orders = con.execute("SELECT COUNT(*) c FROM orders WHERE account_id = ?",
                           (a["account_id"],)).fetchone()["c"]
    if inherited or n_orders or con.execute("SELECT 1 FROM trades WHERE account_id=? LIMIT 1",
                                       (a["account_id"],)).fetchone():
        return
    t = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id = ?"
                    " ORDER BY effective_date DESC, created_at DESC, target_id DESC LIMIT 1", (a["account_id"],)).fetchone()
    if not t:
        return
    from src.forward.execution import create_orders as _co
    floor = today
    if competition["managed"]:
        floor = max(floor, competition["start_date"])
    if a["participant_id"]:
        pa = con.execute("SELECT account_id FROM accounts WHERE participant_id=? AND account_type='personal'", (a["participant_id"],)).fetchone()
        pd = latest_decision(con, pa["account_id"]) if pa else None
        if competition["managed"] and pa:
            pd = initial_decision(con, pa["account_id"]) or pd
        if pd:
            floor = max(floor, str(pd["effective_date"])[:10])
    _co(con, a["account_id"], _json.loads(t["weights_json"]), now_iso(), floor,
        ft["benchmark_version"], a["participant_id"], kind="INITIAL_BENCHMARK_ORDER")
    log_event(con, "INITIAL_BENCHMARK_ORDER_CREATED", ft["benchmark_version"],
              a["participant_id"], a["account_id"], {"effective": today})


@guarded_batch
def _execute_daily(con, cfg, today, *, use_stored_prices=False):
    from src.forward.competition import policy
    current = policy(con)
    if current.get("reason") == "REPLAY_SCOPED_EXECUTION_REQUIRED":
        return 0, {"status": "COMPETITION_WAIT", "outcome": "PARTIAL", "retryable": True,
                   "reason": current["reason"], "valuated": 0}
    from src.forward.prices import refresh_live
    ft = cfg["forward_test"]
    frozen_w, frozen_meta = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
    versions = versions_from_cfg(cfg)

    from src.forward.db import log_event as _log_event
    stale_days = int(ft.get("stale_price_days", 14))
    try:
        rep = ({"asof": today, "new_points": 0, "stale": [], "source": "stored-prices"}
               if use_stored_prices else refresh_live(con, tickers_map(con, frozen_meta)))
    except Exception as exc:  # noqa: BLE001 - 수집 실패는 반드시 기록한다
        _log_event(con, "PRICE_REFRESH_FAILED", ft["benchmark_version"],
                   payload={"error": str(exc)[:500], "asof": today})
        con.commit()
        raise
    print(f"refresh: {rep}")
    asof = rep["asof"]
    price_report = refresh_payload(con, rep, stale_days)
    _log_event(con, "STORED_PRICES_USED" if use_stored_prices else "PRICE_REFRESH",
               ft["benchmark_version"], payload=price_report)
    con.commit()
    if price_report["stale_assets"]:
        print(f"WARNING: stale prices ({stale_days}d+): {price_report['stale_assets']}")

    competition = policy(con)
    if competition["managed"] and competition["blocked"]:
        pending = con.execute("SELECT COUNT(*) c FROM orders WHERE status='pending'").fetchone()["c"]
        print(f"Competition waiting: {competition.get('reason')}; "
              f"READY {competition.get('ready', 0)}/{competition.get('required', 0)}; no orders, fills or NAV.")
        return 0, {"status": "COMPETITION_WAIT", "outcome": "PARTIAL", "retryable": True,
            "reason": competition.get("reason"),
            "ready": competition.get("ready", 0), "required": competition.get("required", 0),
            "start_date": competition.get("start_date"), "asof": asof,
            "new_points": price_report["new_points"], "pending": pending, "valuated": 0,
            "fetch_failed": price_report["fetch_failed"], "stale_assets": price_report["stale_assets"]}

    from src.forward.decision_policy import awaiting_confirmation
    accounts = [dict(r) for r in con.execute("SELECT * FROM accounts WHERE status='active'").fetchall()]
    accounts = [a for a in accounts if not awaiting_confirmation(con, a)]
    if competition["managed"]:
        enrolled = {a for m in competition["schedule"]["members"] for a in m["account_ids"]}
        accounts = [a for a in accounts if a["account_id"] in enrolled]
    from src.forward.db import log_event
    from src.forward.state import live_orders_blocked
    blocked, blocked_reason = live_orders_blocked(con)
    if blocked:
        print(f"order creation blocked: {blocked_reason}")
    # FX alone never advances an investable observation; future rows are ignored.
    maxdate = con.execute("SELECT MAX(date) m FROM prices_daily WHERE asset_id != '__FX__' AND date <= ?",
                          (asof,)).fetchone()["m"]
    results, account_errors, waiting_accounts, price_wait_accounts = {}, {}, [], []
    for a in accounts:
        aid = a["account_id"]
        stage = "orders"
        try:
            with _account_transaction(con, aid) as tx:
                if not blocked:
                    _create_account_orders(tx, a, competition, asof, today, ft)
                stage = "execution"
                fills = execute_pending(tx, aid, asof,
                            float(ft["costs"]["trading_cost_bps"]), ft["benchmark_version"],
                            a["participant_id"])
                first = tx.execute("SELECT MIN(execution_at) m FROM trades WHERE account_id = ?",
                                   (aid,)).fetchone()["m"]
                if fills and first == asof:
                    log_event(tx, "INITIAL_BENCHMARK_EXECUTED", ft["benchmark_version"],
                              a["participant_id"], aid, {"first_execution_date": first})
                stage = "valuation"
                r = (valuate(tx, aid, maxdate, versions, float(a["initial_capital_krw"]), stale_days)
                     if maxdate else {"status": "NAV_INCOMPLETE", "reason": "no stored investable prices"})
                expected_wait = bool(r.get("missing")) or r.get("reason") in (
                    "no executions yet", "competition not started for this valuation",
                    "no stored investable prices")
                if r["status"] == "NAV_INCOMPLETE" and not expected_wait:
                    raise RuntimeError("valuation incomplete")
                # Future-effective redesign orders need not block today's job.
                pending = tx.execute("SELECT 1 FROM orders WHERE account_id=? AND status='pending' AND effective_at<=? LIMIT 1",
                                     (aid, asof)).fetchone()
            results[aid] = r
            if expected_wait or pending:
                waiting_accounts.append(aid)
                price_wait_accounts.append(aid)
        except Exception as exc:
            # The account transaction rolled back, including counters and events.
            # Only type/stage/id are recorded: exception text can contain secrets.
            error = {"stage": stage, "error_type": type(exc).__name__}
            account_errors[aid] = error
            print(f"ACCOUNT_FAILED: {aid} {stage} {error['error_type']}")
            try:
                log_event(con, "DAILY_ACCOUNT_FAILED", ft["benchmark_version"],
                          a["participant_id"], aid, error)
                con.commit()
            except Exception:
                con.rollback()
                print(f"ACCOUNT_FAILURE_AUDIT_UNAVAILABLE: {aid}")
    # Preserve lifecycle latch after committed account work only.
    latch_first_execution(con, ft["benchmark_version"])
    con.commit()

    # ---- guardrails ----
    fails = [f"{aid}: {e['stage']} {e['error_type']}" for aid, e in account_errors.items()]
    partials = []
    if not accounts:
        partials.append("no eligible accounts")
    for aid, r in results.items():
        if r["status"] == "NAV_INCOMPLETE" and r.get("reason") == "competition not started for this valuation":
            partials.append(f"{aid}: awaiting prices on/after competition T0 (no NAV yet)")
        elif r["status"] == "NAV_INCOMPLETE" and r.get("reason") in ("no executions yet", "no stored investable prices"):
            partials.append(f"{aid}: awaiting first execution (no NAV yet)")
        elif r["status"] == "NAV_INCOMPLETE" and r.get("missing"):
            partials.append(f"{aid}: valuation price missing")
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
        con.rollback()
        partials.append(f"risk check unavailable: {type(e).__name__}")

    valuated = sum(r["status"] in ("OK", "STALE_PRICE") for r in results.values())
    print(f"saved NAV for {valuated} accounts at {maxdate}; pending orders: {pend}")
    stats = {"asof": maxdate, "valuated": valuated, "attempted_accounts": len(accounts), "pending": pend,
             "new_points": price_report["new_points"],
             "fetch_failed": price_report["fetch_failed"],
             "stale_assets": price_report["stale_assets"],
             "account_results": results, "account_errors": account_errors,
             "waiting_accounts": waiting_accounts, "price_wait_accounts": price_wait_accounts,
             "retryable": bool(fails or partials or waiting_accounts)}
    successful = sum(aid not in waiting_accounts and r["status"] == "OK"
                     for aid, r in results.items())
    stats["successful_accounts"] = successful
    if fails:
        stats["outcome"] = "PARTIAL" if successful else "FAILED"
        print("FAIL:")
        for f in fails:
            print(f"  - {f}")
        print("STATUS: FAIL")
        stats["status"] = "FAIL"
        print(f"OUTCOME: {stats['outcome']}")
        return 1, stats
    if partials or waiting_accounts:
        stats["outcome"] = "PARTIAL"
        print("PARTIAL:")
        for p in partials:
            print(f"  - {p}")
        print("STATUS: PARTIAL")
        stats["status"] = "PARTIAL"
        print("OUTCOME: PARTIAL")
        return 0, stats
    print("STATUS: PASS")
    stats["status"] = "PASS"  # Existing local/report contract.
    stats["outcome"] = "SUCCESS"
    print("OUTCOME: SUCCESS")
    return 0, stats


if __name__ == "__main__":
    raise SystemExit(main())
