"""Validation replay: full forward-test loop on SYNTHETIC prices (2025-01→2026-09).

Proves orders/execution/NAV/attribution/ranking end-to-end on realistic-length
history. Outputs go to outputs/forward/validation/ and data/forward_validation.db.
Nothing here touches the live forward DB or real history interpretation.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.forward.accounts import (ensure_personal_accounts, place_target_orders, record_target,
                                  versions_from_cfg)
from src.forward.briefing import export_latest, plots, render_dashboard, weekly_snapshot
from src.forward.config import load_forward_config
from src.forward.db import connect, init_db, log_event
from src.forward.runtime import print_banner
from src.forward.execution import execute_pending
from src.forward.frozen import load_frozen_benchmark
from src.forward.ledger import valuate
from src.forward.metrics import nav_frame
from src.forward.participants import add_participant
from src.forward.portfolio import build_personalized
from src.forward.prices import CORE_IDS, theme_asset_id, upsert_prices
from src.forward.risk import build_cov_asof
from src.forward.themes import register_themes
from src.forward.views import active_views, close_view, mark_held, submit_view
from src.forward.run_weekly import batch_views

THEMES = ["semiconductor", "ai", "nuclear"]
VIEWS_SCRIPT = [
    # (date, participant_idx, action, theme, reason)
    ("2025-02-06T10:00:00+00:00", 0, "submit", "ai", "scripted-ai"),
    ("2025-02-06T11:00:00+00:00", 1, "submit", "nuclear", "scripted-nuclear"),
    ("2025-03-06T10:00:00+00:00", 0, "submit", "semiconductor", "scripted-semi"),
    ("2025-04-03T10:00:00+00:00", 2, "submit", "semiconductor", "scripted-semi"),
    ("2025-05-01T10:00:00+00:00", 0, "close", "ai", ""),
    ("2025-06-12T10:00:00+00:00", 2, "close", "semiconductor", ""),
]


def synth_panel():
    idx = pd.bdate_range("2023-06-01", "2026-09-11")
    rng = np.random.default_rng(1234)
    drift = {"us_equity": 0.0004, "developed_ex_us": 0.0003, "emerging_markets": 0.0005,
             "korea_equity": 0.0004, "us_treasury": 0.0001, "korea_treasury": 0.0001,
             "tips": 0.0001, "gold": 0.0003, "global_reit": 0.0003,
             theme_asset_id("semiconductor"): 0.0008, theme_asset_id("ai"): 0.0007,
             theme_asset_id("nuclear"): 0.0009}
    vol = {"us_equity": 0.008, "developed_ex_us": 0.008, "emerging_markets": 0.010,
           "korea_equity": 0.012, "us_treasury": 0.004, "korea_treasury": 0.002,
           "tips": 0.004, "gold": 0.009, "global_reit": 0.009,
           theme_asset_id("semiconductor"): 0.013, theme_asset_id("ai"): 0.014,
           theme_asset_id("nuclear"): 0.030}
    return pd.DataFrame({a: 100 * np.cumprod(1 + rng.normal(drift[a], vol[a], len(idx)))
                         for a in drift}, index=idx)


def main() -> int:
    print_banner("validation")
    cfg = load_forward_config()
    ft = cfg["forward_test"]
    dbp = ROOT / "data" / "forward_validation.db"
    if dbp.exists():
        dbp.unlink()
    con = connect(dbp)
    init_db(con)
    register_themes(con, {"universe_version": "THEME_UNIVERSE_V0.1", "themes": [
        {"theme_id": t, "display_name": t, "theme_type": "theme", "ticker": "SYN",
         "market": "US", "currency": "USD", "active": True, "valid_from": "2025-01-01",
         "valid_to": None, "universe_version": "THEME_UNIVERSE_V0.1"} for t in THEMES]})
    upsert_prices(con, synth_panel(), "synthetic-gbm")
    frozen_w, _ = load_frozen_benchmark(ROOT / "outputs" / "frozen" / "CORE_V0.3")
    versions = versions_from_cfg(cfg)
    mv = ft["benchmark_version"]
    pids = [add_participant(con, n, "2025-02-03", mv) for n in ("Replay Ann", "Replay Ben", "Replay Cat")]
    for pid in pids:
        core_id, pers_id = ensure_personal_accounts(con, pid, "2025-02-03", cfg, mv)
        for aid in (core_id, pers_id):
            record_target(con, aid, dict(frozen_w), "2025-02-03", "core", versions, mv, pid)
            place_target_orders(con, aid, dict(frozen_w), "2025-02-03T00:00:00+00:00",
                                "2025-02-03", mv, pid, kind="INCEPTION_EXECUTION")

    dates = [r["date"] for r in con.execute(
        "SELECT DISTINCT date FROM prices_daily ORDER BY date").fetchall()]
    fridays = sorted({(pd.Timestamp(d) + pd.offsets.Week(weekday=4)).date().isoformat()
                      for d in dates})
    script = sorted(VIEWS_SCRIPT)
    checks = {"guardrail_scaled": 0, "trades": 0, "briefings": 0}
    prev_month = None
    for fri in [f for f in fridays if "2025-02-06" <= f <= "2026-09-04"]:
        month = fri[:7]
        if month != prev_month:
            # monthly core rebalance (drift correction vs holdings)
            from src.forward.views import next_weekday as _nwd
            from src.forward.execution import current_weights as _cw
            eff = _nwd(fri)
            for r in con.execute("SELECT * FROM accounts WHERE account_type='core'").fetchall():
                record_target(con, r["account_id"], dict(frozen_w), eff, "core",
                              versions, mv, r["participant_id"])
                place_target_orders(con, r["account_id"], dict(frozen_w),
                                    f"{fri}T23:59:59+00:00", eff, mv,
                                    r["participant_id"], kind="CORE_REBALANCE",
                                    baseline=_cw(con, r["account_id"], fri))
            prev_month = month
        # views due this cycle: submitted dated within (prev_fri, fri]
        due = [s for s in script if _cycle_of(s[0]) == fri]
        for ts, pi, act, theme, reason in due:
            if act == "submit":
                submit_view(con, pids[pi], theme, ts, reason, "THEME_UNIVERSE_V0.1", mv,
                            int(ft["weekly_view"]["max_active_themes"]),
                            ft["view_schedule"]["cutoff_time"])
            else:
                try:
                    close_view(con, pids[pi], theme, ts, mv)
                except ValueError:
                    pass
        from src.forward.views import next_weekday
        effective = next_weekday(fri)
        cov, _ = build_cov_asof(con, list(CORE_IDS) + [theme_asset_id(t) for t in THEMES],
                                fri, 1, 52)
        for pid in pids:
            submitted = [v for v in active_views(con, pid) if v["cycle_week"] == fri]
            if not submitted:
                mark_held(con, pid, fri, mv)
            tids = sorted({theme_asset_id(v["theme_id"])
                           for v in batch_views(con, pid, fri, effective)})
            res = build_personalized(frozen_w, tids, cfg, cov)
            checks["guardrail_scaled"] += 1 if res["scaled"] else 0
            acc = con.execute("SELECT account_id FROM accounts WHERE participant_id = ?"
                              " AND account_type='personal'", (pid,)).fetchone()["account_id"]
            import json as _json
            prev = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id = ?"
                               " AND effective_date < ? ORDER BY effective_date DESC LIMIT 1",
                               (acc, effective)).fetchone()
            prev_w = _json.loads(prev["weights_json"]) if prev else {}
            record_target(con, acc, res["weights"], effective, "personal", versions, mv, pid)
            place_target_orders(con, acc, res["weights"], f"{fri}T23:59:59+00:00", effective,
                                mv, pid, kind="ACTIVE_REBALANCE", baseline=prev_w)
        # execute + valuate every session up to next friday
        for d in [x for x in dates if fri < x]:
            if dates.index(d) > dates.index(fri) + 7:
                break
            for r in con.execute("SELECT * FROM accounts").fetchall():
                execute_pending(con, r["account_id"], d,
                                float(ft["costs"]["trading_cost_bps"]), mv, r["participant_id"])
                valuate(con, r["account_id"], d, versions,
                        float(r["initial_capital_krw"]), 14)
    con.commit()
    out = ROOT / "outputs" / "forward" / "validation"
    out.mkdir(parents=True, exist_ok=True)
    export_latest(con, cfg, out)
    plots(con, out)
    render_dashboard(con, out)
    checks["trades"] = con.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"]
    # assertions: full loop integrity
    assert checks["trades"] > 100, "expected many paper trades"
    for r in con.execute("SELECT * FROM accounts").fetchall():
        nav = nav_frame(con, r["account_id"])
        assert len(nav) > 100 and (nav["nav"] > 0).all()
        h = con.execute("SELECT date, SUM(weight) s FROM holdings_daily WHERE account_id = ?"
                        " GROUP BY date", (r["account_id"],)).fetchall()
        n = {x["date"]: (x["nav"], x["cash_balance"]) for x in
             con.execute("SELECT date, nav, cash_balance FROM nav_daily WHERE account_id = ?",
                         (r["account_id"],)).fetchall()}
        for x in h:
            assert abs((x["s"] + n[x["date"]][1] / n[x["date"]][0]) - 1.0) < 1e-6
    costs = con.execute("SELECT SUM(transaction_cost) c FROM trades").fetchone()["c"]
    assert costs > 0
    import pandas as _pd
    rk = _pd.read_csv(out / "participant_rankings.csv")
    assert len(rk) == 3 and rk["weekly_active_return"].notna().all()
    assert rk["cum_active_common"].notna().all()
    # ranking sorted by weekly active return desc
    assert (rk["weekly_active_return"].to_numpy()[:-1]
            >= rk["weekly_active_return"].to_numpy()[1:]).all()
    print({"trades": checks["trades"], "scaled_batches": checks["guardrail_scaled"],
           "costs": round(costs, 2)})
    print("REPLAY STATUS: PASS")
    return 0


def _cycle_of(ts: str) -> str:
    from src.forward.views import cutoff_info
    return cutoff_info(ts)[0]


if __name__ == "__main__":
    raise SystemExit(main())
