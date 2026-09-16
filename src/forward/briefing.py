"""Briefing outputs: CSVs, plots, weekly snapshots, static HTML dashboard."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .metrics import attribution, nav_frame, perf_metrics, tracking_ir
from .views import active_views


def _save(fig, path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def account_nav_table(con: sqlite3.Connection, account_type: str | None = None) -> pd.DataFrame:
    q = ("SELECT a.account_id, a.participant_id, a.account_type, a.shadow_name,"
         " n.date, n.nav, n.nav_base100, n.daily_return, n.cumulative_return,"
         " n.cash_balance, n.nav_status FROM accounts a JOIN nav_daily n"
         " ON a.account_id = n.account_id")
    args: tuple = ()
    if account_type:
        q += " WHERE a.account_type = ?"
        args = (account_type,)
    q += " ORDER BY a.account_id, n.date"
    return pd.DataFrame([dict(r) for r in con.execute(q, args).fetchall()])


def export_latest(con: sqlite3.Connection, cfg: dict, outdir) -> dict:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ft = cfg["forward_test"]
    core = account_nav_table(con, "core")
    shadow = account_nav_table(con, "shadow")
    personal = account_nav_table(con, "personal")
    core.to_csv(outdir / "core_nav.csv", index=False)
    shadow.to_csv(outdir / "shadow_nav.csv", index=False)
    personal.to_csv(outdir / "participant_nav.csv", index=False)

    parts = [dict(r) for r in con.execute(
        "SELECT * FROM participants ORDER BY participant_id").fetchall()]
    perf_rows, rank_rows = [], []
    core_by_part = {r["participant_id"]: r["account_id"] for r in con.execute(
        "SELECT participant_id, account_id FROM accounts WHERE account_type='core'").fetchall()}
    for p in parts:
        pid = p["participant_id"]
        acc = con.execute("SELECT account_id FROM accounts WHERE participant_id = ?"
                          " AND account_type = 'personal'", (pid,)).fetchone()
        if acc is None:
            continue
        nav = nav_frame(con, acc["account_id"])
        pm = perf_metrics(nav)
        crow = core_by_part.get(pid)
        ti = tracking_ir(nav, nav_frame(con, crow)) if crow else {}
        perf_rows.append({"participant_id": pid, "display_name": p["display_name"],
                          "status": p["status"], **{k: v for k, v in {**pm, **ti}.items()
                                                    if k != "status"},
                          "perf_status": pm.get("status")})
        if nav.empty:
            continue
        last = nav.iloc[-1]
        week = nav.iloc[-5:] if len(nav) >= 5 else nav
        rank_rows.append({"participant_id": pid, "display_name": p["display_name"],
                          "nav": float(last["nav"]),
                          "weekly_active_return": None, "cum_active": ti.get("active_cumulative"),
                          "mdd": pm.get("mdd"), "te": ti.get("tracking_error"),
                          "ir": ti.get("information_ratio")})
    pd.DataFrame(perf_rows).to_csv(outdir / "participant_performance.csv", index=False)
    # weekly active return needs core counterpart per participant
    for r in rank_rows:
        pid = r["participant_id"]
        acc = con.execute("SELECT account_id FROM accounts WHERE participant_id = ?"
                          " AND account_type = 'personal'", (pid,)).fetchone()
        crow = core_by_part.get(pid)
        if acc and crow:
            pn, cn = nav_frame(con, acc["account_id"]), nav_frame(con, crow)
            idx = pn.index.intersection(cn.index)
            if len(idx) >= 2:
                w = idx[-5:] if len(idx) >= 5 else idx
                r["weekly_active_return"] = float(
                    (pn.loc[w, "nav"].iloc[-1] / pn.loc[w, "nav"].iloc[0]) /
                    (cn.loc[w, "nav"].iloc[-1] / cn.loc[w, "nav"].iloc[0]) - 1.0)
    # common-period: intersection across all personalized + core NAVs
    navs_p, navs_c = {}, {}
    for p in parts:
        acc = con.execute("SELECT account_id FROM accounts WHERE participant_id = ?"
                          " AND account_type = 'personal'", (p["participant_id"],)).fetchone()
        crow = core_by_part.get(p["participant_id"])
        if acc and crow:
            navs_p[p["participant_id"]] = nav_frame(con, acc["account_id"])
            navs_c[p["participant_id"]] = nav_frame(con, crow)
    common = None
    for pid in navs_p:
        idx = navs_p[pid].index.intersection(navs_c[pid].index)
        common = idx if common is None else common.intersection(idx)
    for r in rank_rows:
        pid = r["participant_id"]
        if common is not None and len(common) >= 2 and pid in navs_p:
            pn, cn = navs_p[pid].loc[common], navs_c[pid].loc[common]
            r["cum_active_common"] = float(
                (pn["nav"].iloc[-1] / pn["nav"].iloc[0]) /
                (cn["nav"].iloc[-1] / cn["nav"].iloc[0]) - 1.0)
        else:
            r["cum_active_common"] = None
    rank_rows.sort(key=lambda r: (r["weekly_active_return"] is None,
                                  -(r["weekly_active_return"] or 0)))
    pd.DataFrame(rank_rows).to_csv(outdir / "participant_rankings.csv", index=False)

    views = [dict(r) for r in con.execute("SELECT * FROM views ORDER BY submitted_at").fetchall()]
    maxpx = con.execute("SELECT MAX(date) m FROM prices_daily").fetchone()["m"]
    for v in views:
        v["cycle_date"] = v.get("cycle_date") or v["cycle_week"]
        v["first_execution_at"] = None
        v["lifecycle"] = v["status"] if v["status"] in ("rejected", "closed") else None
        if v["status"] in ("new", "hold") and v["end_at"] is None:
            from src.forward.prices import theme_asset_id
            acc = con.execute("SELECT account_id FROM accounts WHERE participant_id = ?"
                              " AND account_type='personal'", (v["participant_id"],)).fetchone()
            if acc:
                t = con.execute("SELECT MIN(execution_at) m FROM trades WHERE account_id = ?"
                                " AND asset_id = ? AND execution_at >= ?",
                                (acc["account_id"], theme_asset_id(v["theme_id"]),
                                 v["effective_at"])).fetchone()
                v["first_execution_at"] = t["m"] if t else None
            if v["effective_at"] > (maxpx or ""):
                v["lifecycle"] = "PENDING_EFFECTIVE"
            elif v["first_execution_at"] is None:
                v["lifecycle"] = "PENDING_EXECUTION"
            else:
                v["lifecycle"] = "EXECUTED"
        elif v["status"] == "new" or v["status"] == "hold":
            v["lifecycle"] = "VIEW_ACCEPTED"
    pd.DataFrame(views).to_csv(outdir / "current_views.csv", index=False)
    tg = [dict(r) for r in con.execute(
        "SELECT * FROM portfolio_targets ORDER BY account_id, effective_date").fetchall()]
    pd.DataFrame(tg).to_csv(outdir / "current_weights.csv", index=False)
    attr_rows = []
    for p in parts:
        acc = con.execute("SELECT account_id FROM accounts WHERE participant_id = ?"
                          " AND account_type = 'personal'", (p["participant_id"],)).fetchone()
        crow = core_by_part.get(p["participant_id"])
        if acc and crow:
            nav = nav_frame(con, acc["account_id"])
            if len(nav) >= 2:
                a = attribution(con, acc["account_id"], crow,
                                str(nav.index[0].date()), str(nav.index[-1].date()))
                attr_rows.append({"participant_id": p["participant_id"], **{
                    k: (json.dumps(v) if isinstance(v, dict) else v)
                    for k, v in a.items()}})
    pd.DataFrame(attr_rows).to_csv(outdir / "active_contribution.csv", index=False)
    pend = [dict(r) for r in con.execute(
        "SELECT * FROM orders WHERE status = 'pending' ORDER BY effective_at").fetchall()]
    pd.DataFrame(pend).to_csv(outdir / "pending_orders.csv", index=False)

    npx = con.execute("SELECT COUNT(*) c FROM prices_daily").fetchone()["c"]
    lastpx = con.execute("SELECT MAX(date) m FROM prices_daily").fetchone()["m"]
    lastnav = con.execute("SELECT MAX(date) m FROM nav_daily").fetchone()["m"]
    first_exec = con.execute("SELECT MIN(execution_at) m FROM trades").fetchone()["m"]
    inception_date = None
    first_exec_state = None
    try:
        from src.forward.state import get_state as _get_state
        inception_date = _get_state(con, "forward_test_inception_at")
        first_exec_state = _get_state(con, "first_execution_at")
    except Exception:
        pass
    demo_hit = con.execute("SELECT COUNT(*) c FROM participants WHERE display_name LIKE 'Demo %'"
                           ).fetchone()["c"]
    demo_ev = con.execute("SELECT COUNT(*) c FROM events WHERE payload_json LIKE '%Demo %'"
                          ).fetchone()["c"]
    from src.forward.runtime import get_database_path, get_runtime_profile
    profile = get_runtime_profile()
    bench_meta = {}
    try:
        from src.forward.config import resolve as _resolve
        from src.forward.frozen import load_frozen_benchmark
        _, bench_meta = load_frozen_benchmark(_resolve(cfg["frozen_dir"]))
    except Exception:
        pass
    status = {
        "profile": profile,
        "database_path": str(get_database_path(profile)),
        "benchmark_model_date": (bench_meta.get("run_timestamp", "") or "")[:10],
        "benchmark_snapshot_date": bench_meta.get("data_end"),
        "forward_test_inception_at": inception_date,
        "first_execution_at": first_exec_state or first_exec,
        "forward_test_inception": inception_date or "NOT STARTED",
        "first_execution": (first_exec_state or first_exec) or "NOT STARTED",
        "latest_market_data_date": lastpx, "latest_valuation_date": lastnav,
        "benchmark_version": ft["benchmark_version"],
        "theme_universe_version": ft["theme_universe_version"],
        "active_participants": sum(1 for p in parts if p["status"] == "active"),
        "inactive_participants": sum(1 for p in parts if p["status"] != "active"),
        "participant_count": len(parts),
        "demo_contamination": bool(demo_hit or demo_ev),
        "pending_orders": len(pend),
        "price_points": npx,
    }
    (outdir / "system_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def weekly_snapshot(con: sqlite3.Connection, cfg: dict, week_label: str, root) -> Path:
    d = Path(root) / "weekly" / week_label
    d.mkdir(parents=True, exist_ok=True)
    latest = Path(root) / "latest"
    ren = {"weekly_briefing.csv": "participant_rankings.csv",
           "weekly_rankings.csv": "participant_rankings.csv",
           "weekly_views.csv": "current_views.csv",
           "weekly_performance.csv": "participant_performance.csv",
           "weekly_attribution.csv": "active_contribution.csv"}
    for dst, srcn in ren.items():
        s = latest / srcn
        if s.exists():
            (d / dst).write_bytes(s.read_bytes())
    return d


def plots(con: sqlite3.Connection, outdir) -> None:
    outdir = Path(outdir)
    core = account_nav_table(con, "core")
    shadow = account_nav_table(con, "shadow")
    personal = account_nav_table(con, "personal")
    if (not core.empty or not shadow.empty) and "account_id" in core.columns:
        fig, ax = plt.subplots(figsize=(10, 5))
        groups = []
        if not core.empty:
            groups += list(core.groupby("account_id"))
        if not shadow.empty:
            groups += list(shadow.groupby("account_id"))
        for name, g in groups:
            lab = name if str(name).startswith("A-SHADOW") else "core"
            ax.plot(pd.to_datetime(g["date"]), g["nav_base100"], label=lab)
        ax.set_title("Core vs Shadow NAV (base 100)")
        ax.legend(fontsize=8)
        fig.tight_layout()
        _save(fig, outdir / "core_vs_shadow_nav.png")
    if not personal.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        for name, g in personal.groupby("account_id"):
            ax.plot(pd.to_datetime(g["date"]), g["nav_base100"], label=name)
        ax.set_title("Participant personalized NAVs (base 100)")
        ax.legend(fontsize=8)
        fig.tight_layout()
        _save(fig, outdir / "participant_navs.png")
        # drawdown of first personal account
        g0 = personal.groupby("account_id").get_group(
            sorted(personal["account_id"].unique())[0]).sort_values("date")
        nav = g0["nav_base100"].to_numpy(float)
        dd = nav / np.maximum.accumulate(nav) - 1.0
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.fill_between(pd.to_datetime(g0["date"]), dd * 100, 0, alpha=0.4)
        ax.set_title("Drawdown (%) — sample account")
        fig.tight_layout()
        _save(fig, outdir / "drawdown.png")
    rk = outdir / "participant_rankings.csv"
    try:
        df = pd.read_csv(rk) if rk.stat().st_size > 0 else pd.DataFrame()
    except Exception:
        df = pd.DataFrame()
    df = df[df["weekly_active_return"].notna()] if "weekly_active_return" in df.columns else df
    if not df.empty:
            fig, ax = plt.subplots(figsize=(8, max(3, len(df))))
            ax.barh(df["display_name"], df["weekly_active_return"] * 100)
            ax.set_xlabel("Weekly active return (%)")
            ax.set_title("Active return ranking")
            fig.tight_layout()
            _save(fig, outdir / "active_return_ranking.png")


def render_dashboard(con: sqlite3.Connection, outdir) -> Path:
    outdir = Path(outdir)
    status = json.loads((outdir / "system_status.json").read_text(encoding="utf-8")) \
        if (outdir / "system_status.json").exists() else {}
    try:
        rk = pd.read_csv(outdir / "participant_rankings.csv") \
            if (outdir / "participant_rankings.csv").stat().st_size > 0 else pd.DataFrame()
    except Exception:
        rk = pd.DataFrame()
    rows = "".join(
        f"<tr><td>{r.get('display_name')}</td><td>{(r.get('weekly_active_return') or 0):.3%}</td>"
        f"<td>{(r.get('cum_active') or 0):.3%}</td><td>{(r.get('mdd') or 0):.2%}</td>"
        f"<td>{(r.get('te') or 0):.2%}</td></tr>" for _, r in rk.iterrows())
    pngs = "".join(f'<div><h3>{p.stem}</h3><img src="{p.name}" style="max-width:100%"></div>'
                   for p in sorted(outdir.glob("*.png")))
    html = f"""<html><head><meta charset="utf-8"><title>Forward Test Dashboard</title></head>
<body><h1>Forward Test Dashboard (paper trading, CORE_V0.3 frozen)</h1>
<h2>System status</h2><pre>{json.dumps(status, indent=2)}</pre>
<h2>Ranking (weekly active return)</h2>
<table border="1"><tr><th>Participant</th><th>Weekly active</th><th>Cum active</th>
<th>MDD</th><th>TE</th></tr>{rows}</table>
<h2>Charts</h2>{pngs}</body></html>"""
    (outdir / "dashboard.html").write_text(html, encoding="utf-8")
    return outdir / "dashboard.html"
