"""Core Benchmark V0.3 pipeline (Phase 1.6).

Black-Litterman stabilization: Neutral-implied equilibrium prior + low-
confidence external CMA views -> posterior -> 60/40 risk-anchored max-return.
V0.2 (direct CMA), Neutral, Tangency, Equal Weight all preserved.

Usage (run from robo-advisor/):
    python -m src.pipeline.run_core_v0 [--data-mode live|snapshot]
Phase 1.6 uses the frozen snapshot: prefer --data-mode snapshot.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.data.market_data import fetch_universe_daily
from src.data.preprocessing import build_krw_weekly_returns
from src.data.snapshot import load_snapshot, save_snapshot
from src.expected_return.black_litterman import bl_full_pass
from src.expected_return.conversions import geometric_to_arithmetic
from src.expected_return.strategic_v0 import build_optimizer_mu
from src.pipeline.plots import plot_correlation, plot_nav
from src.pipeline.plots_v02 import (
    plot_er_sensitivity,
    plot_frontier_v02,
    plot_horizon_sensitivity,
    plot_weights_compare,
)
from src.pipeline.plots_v03 import (
    plot_bl_er_compare,
    plot_confidence_path,
    plot_sensitivity_compare,
    plot_weights_v03,
)
from src.portfolio.bl_benchmark import build_bl_portfolio
from src.portfolio.comparators import equal_weight, sixty_forty
from src.portfolio.constraints import ASSET_ORDER, validate_weights
from src.portfolio.frontier import build_frontier
from src.portfolio.metrics import portfolio_return_series, summarize_series
from src.portfolio.optimizer import max_return_with_vol_cap, max_sharpe, portfolio_stats
from src.portfolio.reference import (
    FULL_ORDER,
    extend_cov_with_cash,
    extend_mu_with_cash,
    neutral_60_40_weights,
    reference_return,
    reference_vol,
)
from src.portfolio.sensitivity import (
    shock_mu,
    summarize_bound_hits,
    weight_l1_diff,
    zero_weight_report,
)
from src.risk.covariance import (
    annualize_covariance,
    corr_from_cov,
    ledoit_wolf_covariance,
    vols_from_cov,
)
from src.risk.drawdown import max_drawdown
from src.risk.returns import slice_lookback
from src.utils.io import ensure_dir, save_csv, save_json


def load_yaml(p: Path) -> dict:
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-mode", choices=["live", "snapshot"], default=None)
    args = ap.parse_args()

    t0 = datetime.now(timezone.utc)
    cfg_assets = load_yaml(ROOT / "config" / "assets.yaml")
    cfg_er = load_yaml(ROOT / "config" / "expected_returns_v0.yaml")
    cfg_opt = load_yaml(ROOT / "config" / "optimizer_v0.yaml")
    assert cfg_opt.get("model_version") == "CORE_V0.3", "optimizer config must be CORE_V0.3"

    order9 = ASSET_ORDER
    order10 = FULL_ORDER
    bounds = cfg_opt["weight_bounds"]
    groups = cfg_opt["group_constraints"]
    rf = float(cfg_opt.get("risk_free_rate", cfg_er["risk_free_rate"]["cash"]))
    opt_cfg = cfg_opt["optimizer"]
    seed = int(cfg_opt["risk"].get("random_seed", 42))
    data_cfg = cfg_opt["data"]
    look_p = int(cfg_opt["risk"].get("primary_lookback_years", 5))
    look_s = int(cfg_opt["risk"].get("sensitivity_lookback_years", 3))
    ann = int(cfg_opt["risk"].get("annualization_factor", 52))
    vol_tol = float(opt_cfg.get("vol_target_tol", 5e-4))
    bl_cfg = cfg_opt.get("bl", {})
    tau = float(bl_cfg.get("tau", 0.05))
    conf_primary = float(bl_cfg.get("primary_confidence", 0.25))
    conf_grid = [float(c) for c in bl_cfg.get("confidence_grid", [0.0, 0.1, 0.25, 0.5, 0.75, 1.0])]
    mode = args.data_mode or str(data_cfg.get("mode", "live"))
    snap_dir = ROOT / str(data_cfg.get("snapshot_dir", "data/snapshots/SNAPSHOT_20260911_V0"))

    # ---- Data (frozen snapshot for Phase 1.6) ----
    if mode == "snapshot":
        prices, fx, stored_ret, stored_px, snap_meta = load_snapshot(snap_dir)
        tickers = snap_meta["tickers"]
        assert set(prices) == set(tickers) - {"FX_USDKRW"}, "snapshot universe mismatch"
        weekly_ret9, weekly_px9, diag = build_krw_weekly_returns(
            prices, fx, cfg_assets,
            max_fill_days=int(data_cfg.get("max_fill_days", 5)),
            weekly_rule=str(data_cfg.get("weekly_rule", "W-FRI")),
        )
        maxdev = float((weekly_ret9.to_numpy() - stored_ret.loc[weekly_ret9.index].to_numpy())
                       .__abs__().max())
        if not (maxdev < 1e-9 and list(weekly_ret9.columns) == list(stored_ret.columns)):
            raise RuntimeError(f"Snapshot weekly returns inconsistent (maxdev={maxdev})")
        print(f"Loaded snapshot from {snap_dir} (no provider call).", flush=True)
    elif mode == "live":
        start = data_cfg.get("start", "2015-01-01")
        end = data_cfg.get("end") or datetime.now(timezone.utc).date().isoformat()
        print("Fetching daily prices (Yahoo chart API)...", flush=True)
        prices, fx, tickers = fetch_universe_daily(cfg_assets, start, end)
        weekly_ret9, weekly_px9, diag = build_krw_weekly_returns(
            prices, fx, cfg_assets,
            max_fill_days=int(data_cfg.get("max_fill_days", 5)),
            weekly_rule=str(data_cfg.get("weekly_rule", "W-FRI")),
        )
        snap_meta = {
            "model_version": "CORE_V0.3",
            "tickers": tickers,
            "fx_treatment": diag.get("fx_treatment", {}),
            "diagnostics": diag,
            "provider": "yahoo_chart",
            "created": t0.isoformat(),
        }
        save_snapshot(snap_dir, prices, fx, weekly_ret9, weekly_px9, snap_meta)
        print(f"Snapshot saved to {snap_dir}.", flush=True)
    else:
        raise ValueError(f"unknown data mode: {mode}")
    data_start, data_end = str(weekly_ret9.index.min().date()), str(weekly_ret9.index.max().date())

    # ---- Risk: 5Y primary + 3Y sensitivity ----
    r5 = slice_lookback(weekly_ret9, look_p)
    r3 = slice_lookback(weekly_ret9, look_s)
    cov_w5 = ledoit_wolf_covariance(r5)
    cov_w3 = ledoit_wolf_covariance(r3)
    cov5 = annualize_covariance(cov_w5, ann)
    cov3 = annualize_covariance(cov_w3, ann)
    vol5 = vols_from_cov(cov5)
    vol3 = vols_from_cov(cov3)
    corr5 = corr_from_cov(cov5)
    corr3 = corr_from_cov(cov3)
    mdd5 = pd.Series({a: max_drawdown(r5[a]) for a in order9})
    cov10_5 = extend_cov_with_cash(cov5)
    cov10_3 = extend_cov_with_cash(cov3)

    # ---- Strategic CMA (now a VIEW, not the optimizer input) ----
    mu_cma9 = build_optimizer_mu(cfg_er, order9)
    mu_cma10 = extend_mu_with_cash(mu_cma9, rf)
    arith_diag = pd.Series({a: geometric_to_arithmetic(float(mu_cma9.loc[a]), float(vol5.loc[a]))
                            for a in order9}, name="arith_diagnostic")
    er_table = pd.DataFrame({"strategic_cma": mu_cma9,
                             "arith_diagnostic": arith_diag,
                             "annual_vol_5y": vol5, "annual_vol_3y": vol3})

    # ---- Reference + Core V0.2 (direct CMA, preserved) ----
    print("Optimizing Core V0.2 (direct CMA, preserved)...", flush=True)
    w_neutral = neutral_60_40_weights(cfg_opt)
    ref_vol5 = reference_vol(w_neutral, cov10_5)
    ref_ret = reference_return(w_neutral, mu_cma10)
    w_v02 = max_return_with_vol_cap(mu_cma10, cov10_5, ref_vol5, order10, bounds, groups,
                                    opt_cfg, seed=seed)
    v02_ret, v02_vol, v02_sh = portfolio_stats(w_v02.to_numpy(float), mu_cma10.to_numpy(float),
                                               cov10_5.to_numpy(float), rf)

    # ---- Core V0.3 (BL posterior) ----
    print("Optimizing Core V0.3 (BL posterior)...", flush=True)
    bl_primary = build_bl_portfolio(mu_cma9, cov5, w_neutral, rf, tau, conf_primary,
                                    bounds, groups, opt_cfg, seed=seed)
    w_v03 = bl_primary["weights"]
    v03_ret, v03_vol, v03_sh = bl_primary["ret"], bl_primary["vol"], bl_primary["sharpe"]
    post9 = bl_primary["posterior_abs"]
    prior9 = bl_primary["prior_abs"]

    # ---- Tangency (diagnostic only) + frontier ----
    w_tan9 = max_sharpe(mu_cma9, cov5, rf, order9, bounds, groups, opt_cfg, seed=seed)
    t_ret, t_vol, t_sh = portfolio_stats(w_tan9.to_numpy(float), mu_cma9.to_numpy(float),
                                         cov5.to_numpy(float), rf)
    frontier = build_frontier(mu_cma9, cov5, rf, order9, bounds, groups, opt_cfg, seed=seed,
                              extra_warm=[w_tan9.to_numpy(float)])

    # ---- Confidence grid ----
    print("Running BL confidence grid...", flush=True)
    conf_rows = []
    conf_weights = {}
    for c in conf_grid:
        if abs(c - conf_primary) < 1e-12:
            res, w_c = bl_primary, w_v03
        else:
            res = build_bl_portfolio(mu_cma9, cov5, w_neutral, rf, tau, c,
                                     bounds, groups, opt_cfg, seed=seed)
            w_c = res["weights"]
        conf_weights[c] = w_c
        l1n, _ = weight_l1_diff(w_c, w_neutral)
        r_, v_, sh_ = res["ret"], res["vol"], res["sharpe"]
        bh = summarize_bound_hits(w_c, bounds)
        zr = zero_weight_report(w_c.loc[order9])
        conf_rows.append({"confidence": c, "port_er": r_, "port_vol": v_, "sharpe": sh_,
                          "l1_vs_neutral": l1n,
                          "n_upper": int((bh.bound_hit == "upper").sum()),
                          "n_zero": int(zr["n_zero"]),
                          **{f"w_{k}": float(w_c.loc[k]) for k in order10}})
    conf_df = pd.DataFrame(conf_rows).sort_values("confidence").reset_index(drop=True)
    # max jump between adjacent grid points
    cw = conf_df[[f"w_{k}" for k in order10]].to_numpy(float)
    max_conf_jump = float(np.abs(np.diff(cw, axis=0)).sum(axis=1).max()) if len(cw) > 1 else 0.0

    # ---- Horizon sensitivity V0.2 + V0.3 (3Y: prior/target rebuilt) ----
    ref_vol3 = reference_vol(w_neutral, cov10_3)
    w_v02_3y = max_return_with_vol_cap(mu_cma10, cov10_3, ref_vol3, order10, bounds, groups,
                                       opt_cfg, seed=seed)
    l1_v02, l1_v02_per = weight_l1_diff(w_v02, w_v02_3y)
    bl_3y = build_bl_portfolio(mu_cma9, cov3, w_neutral, rf, tau, conf_primary,
                               bounds, groups, opt_cfg, seed=seed)
    w_v03_3y = bl_3y["weights"]
    l1_v03, l1_v03_per = weight_l1_diff(w_v03, w_v03_3y)

    # ---- ER shock sensitivity: V0.2 vs V0.3 full paths ----
    print("Running ER shock sensitivity (V0.2 vs V0.3)...", flush=True)
    shocks = [float(x) for x in cfg_opt.get("sensitivity", {}).get(
        "er_shocks", [-0.01, -0.005, 0.005, 0.01])]
    sens_rows, v02_delta05, v03_delta05 = [], {}, {}
    for a in order9:
        for s in shocks:
            mu_s9 = shock_mu(mu_cma9, a, s)
            # V0.2 path: shocked CMA straight into the optimizer
            mu_s10 = extend_mu_with_cash(mu_s9, rf)
            w2 = max_return_with_vol_cap(mu_s10, cov10_5, ref_vol5, order10, bounds, groups,
                                         opt_cfg, seed=seed)
            r2, v2, _ = portfolio_stats(w2.to_numpy(float), mu_s10.to_numpy(float),
                                        cov10_5.to_numpy(float), rf)
            # V0.3 path: shocked CMA -> Q -> BL posterior -> optimizer
            res3 = build_bl_portfolio(mu_s9, cov5, w_neutral, rf, tau, conf_primary,
                                      bounds, groups, opt_cfg, seed=seed)
            w3 = res3["weights"]
            mu3 = res3["mu_bl10"]
            r3_, v3_, _ = portfolio_stats(w3.to_numpy(float), mu3.to_numpy(float),
                                          cov10_5.to_numpy(float), rf)
            sens_rows.append({"shocked_asset": a, "shock": s,
                              "v02_port_ret": r2, "v02_port_vol": v2,
                              "v03_port_ret": r3_, "v03_port_vol": v3_,
                              **{f"v02_w_{k}": float(w2.loc[k]) for k in order10},
                              **{f"v03_w_{k}": float(w3.loc[k]) for k in order10}})
            if abs(s - 0.005) < 1e-12:
                v02_delta05[a] = float(w2.loc[a]) - float(w_v02.loc[a])
                v03_delta05[a] = float(w3.loc[a]) - float(w_v03.loc[a])
    sens_df = pd.DataFrame(sens_rows)
    red_rows, sens_warnings = [], []
    for a in order9:
        d2, d3 = v02_delta05[a], v03_delta05[a]
        # V0.2 delta ~0 (already pinned at a bound): ratio undefined -> null.
        ratio = (1.0 - abs(d3) / abs(d2)) if abs(d2) > 1e-7 else None
        red_rows.append({"asset": a, "v02_delta_pp": d2 * 100, "v03_delta_pp": d3 * 100,
                         "reduction_ratio": ratio})
        lo, hi = float(bounds[a]["min"]), float(bounds[a]["max"])
        for tag, base, dd in (("V0.2", float(w_v02.loc[a]), d2), ("V0.3", float(w_v03.loc[a]), d3)):
            wv = base + dd
            if (abs(base) < 1e-9 and abs(wv - hi) < 1e-6) or \
               (abs(base - hi) < 1e-6 and abs(wv) < 1e-9):
                sens_warnings.append(f"SENSITIVITY_WARNING {tag}: {a} {base:.2%} -> {wv:.2%} on +50bp")
    red_df = pd.DataFrame(red_rows)

    # ---- Stability diagnostics ----
    def stab(w, mu_, cov_, name):
        r_, v_, sh_ = portfolio_stats(w.to_numpy(float), mu_.to_numpy(float),
                                      cov_.to_numpy(float), rf)
        bh = summarize_bound_hits(w, bounds)
        zr = zero_weight_report(w.loc[order9] if set(order9) <= set(w.index) else w)
        l1n, _ = weight_l1_diff(w, w_neutral)
        return {"model": name, "er": r_, "vol": v_, "sharpe": sh_,
                "n_upper": int((bh.bound_hit == "upper").sum()),
                "n_zero_risky": int(zr["n_zero"]),
                "l1_vs_neutral": l1n,
                "er_uplift_vs_neutral": r_ - ref_ret}

    maxshock = lambda dd: float(max(abs(v) for v in dd.values()))
    stab_rows = [stab(w_v02, mu_cma10, cov10_5, "V0.2"), stab(w_v03, bl_primary["mu_bl10"], cov10_5, "V0.3")]
    stab_df = pd.DataFrame(stab_rows)
    stab_df["max_50bp_shock_move"] = [maxshock(v02_delta05), maxshock(v03_delta05)]
    stab_df["horizon_l1"] = [l1_v02, l1_v03]
    bound_v02 = summarize_bound_hits(w_v02, bounds)
    bound_v03 = summarize_bound_hits(w_v03, bounds)
    n_up_v02 = int((bound_v02.bound_hit == "upper").sum())
    n_up_v03 = int((bound_v03.bound_hit == "upper").sum())
    zero_v02 = zero_weight_report(w_v02.loc[order9])
    zero_v03 = zero_weight_report(w_v03.loc[order9])

    # ---- Comparators ----
    w_eq9 = equal_weight(order9)
    w_6040_legacy = sixty_forty(order9)
    v01_path = ROOT / "outputs" / "CORE_V0.1" / "core_benchmark_weights.csv"
    w_v01 = pd.read_csv(v01_path, index_col=0)["weight"] if v01_path.exists() else None

    comp_notes = []
    w_issues = {
        "core_v03": validate_weights(w_v03.to_numpy(float), order10, bounds, groups),
        "core_v02": validate_weights(w_v02.to_numpy(float), order10, bounds, groups),
        "tangency": validate_weights(w_tan9.to_numpy(float), order9, bounds, groups),
        "neutral_60_40": validate_weights(w_neutral.to_numpy(float), order10, bounds, groups),
        "equal_weight": validate_weights(w_eq9.to_numpy(float), order9, bounds, groups),
    }

    # ---- Historical diagnostic (static weights; NOT a walk-forward backtest) ----
    cash_ret = pd.Series(rf / 52.0, index=weekly_ret9.index, name="cash")
    weekly_ret10 = pd.concat([weekly_ret9, cash_ret], axis=1)[order10]
    ports = {"core_v03": w_v03, "core_v02": w_v02, "tangency": w_tan9,
             "neutral_60_40": w_neutral, "equal_weight": w_eq9}
    san_rows = []
    for name, w in ports.items():
        frame = weekly_ret10 if set(w.index) == set(order10) else weekly_ret9
        s = portfolio_return_series(frame[[c for c in w.index]], w)
        mm = summarize_series(s, rf)
        mm["portfolio"] = name
        san_rows.append(mm)
    sanity = pd.DataFrame(san_rows).set_index("portfolio")[
        ["cagr", "ann_vol", "sharpe", "mdd", "ending_wealth", "n_weeks"]]
    if w_v01 is not None:
        arch_w = ROOT / "outputs" / "CORE_V0.1" / "weekly_returns_krw.csv"
        if arch_w.exists():
            warch = pd.read_csv(arch_w, index_col=0, parse_dates=True)
            s01 = portfolio_return_series(warch[[c for c in w_v01.index]], w_v01)
            m01 = summarize_series(s01, rf)
            m01["portfolio"] = "core_v01"
            sanity.loc["core_v01"] = [m01[k] for k in ["cagr", "ann_vol", "sharpe", "mdd",
                                                       "ending_wealth", "n_weeks"]]

    # ---- Comparison table (native expected returns, 5Y cov) ----
    comp_ports = {"neutral_60_40": (w_neutral, mu_cma10, cov10_5),
                  "core_v02": (w_v02, mu_cma10, cov10_5),
                  "core_v03": (w_v03, bl_primary["mu_bl10"], cov10_5),
                  "tangency": (w_tan9, mu_cma9, cov5),
                  "equal_weight": (w_eq9, mu_cma9, cov5)}
    if w_v01 is not None:
        comp_ports["core_v01"] = (w_v01, mu_cma9, cov5)
    comp_table = []
    for name, (w, mu_, cov_) in comp_ports.items():
        r_, v_, sh_ = portfolio_stats(w.to_numpy(float), mu_.loc[w.index].to_numpy(float),
                                      cov_.loc[w.index, w.index].to_numpy(float), rf)
        w10 = w.reindex(order10).fillna(0.0)
        l1n, _ = weight_l1_diff(w10, w_neutral)
        comp_table.append({"portfolio": name, "er": r_, "vol": v_, "sharpe": sh_,
                           "distance_from_neutral": l1n})
    comp_df = pd.DataFrame(comp_table).set_index("portfolio")

    # ---- Validation ----
    issues: list[str] = []
    if not np.allclose(mu_cma9.to_numpy(float),
                       [cfg_er["expected_returns_geometric"][a]["expected_return"] for a in order9]):
        issues.append("strategic CMA view corrupted")
    if cov5.isna().any().any() or cov3.isna().any().any():
        issues.append("covariance contains NaN")
    if np.isnan(bl_primary["posterior_abs"].to_numpy()).any():
        issues.append("BL posterior contains NaN")
    for nm in ("core_v03", "core_v02", "tangency"):
        for x in w_issues[nm]:
            issues.append(f"{nm}: {x}")
    if v03_vol > bl_primary["target_vol"] + vol_tol:
        issues.append(f"core_v03 vol {v03_vol:.4f} > target {bl_primary['target_vol']:.4f} + tol")
    if not np.isfinite(bl_primary["sharpe"]):
        issues.append("core_v03 Sharpe non-finite")
    days_old = (datetime.now(timezone.utc).date() - weekly_ret9.index.max().date()).days
    if mode == "live" and days_old > int(data_cfg.get("freshness_days", 14)):
        issues.append(f"latest data too old: {data_end}")
    for name in ("neutral_60_40", "equal_weight"):
        for x in w_issues[name]:
            comp_notes.append(f"{name}: {x}")
    for x in sens_warnings:
        comp_notes.append(x)
    if n_up_v03 >= 3:
        comp_notes.append("CONCENTRATION WARNING V0.3: >=3 assets at upper bound")
    if n_up_v02 >= 3:
        comp_notes.append("CONCENTRATION WARNING V0.2: >=3 assets at upper bound")
    if zero_v03["level"] != "ok":
        comp_notes.append(f"ZERO_WEIGHT V0.3 {zero_v03['level']}: {zero_v03['zero_assets']}")
    status = "PASS" if not issues else "FAIL"

    # ---- Decision metrics (rule-based suggestion; final call in report) ----
    good, bad = [], []
    if n_up_v03 < n_up_v02:
        good.append("fewer upper-bound hits than V0.2")
    elif n_up_v03 >= 3:
        bad.append("3+ assets still at cap")
    med_red = float(red_df["reduction_ratio"].dropna().median()) if red_df["reduction_ratio"].notna().any() else None
    if med_red is not None and med_red > 0.3:
        good.append(f"median shock-sensitivity reduction {med_red:.0%}")
    elif med_red is not None and med_red <= 0.0:
        bad.append("no median sensitivity reduction")
    if l1_v03 < l1_v02 - 0.05:
        good.append("smaller 3Y/5Y L1 than V0.2")
    elif l1_v03 >= 0.4:
        bad.append("3Y/5Y L1 >= 0.4 persists")
    if maxshock(v03_delta05) >= 0.15:
        bad.append("single-asset shock move >= 15pp persists")
    if max_conf_jump >= 0.20:
        bad.append("confidence-path jump >= 20pp")
    uplift_v03 = float(stab_df.loc[stab_df.model == "V0.3", "er_uplift_vs_neutral"].iloc[0])
    if uplift_v03 < 0.001 and stab_df.loc[stab_df.model == "V0.3", "l1_vs_neutral"].iloc[0] > 0.3:
        bad.append("tiny uplift with large neutral deviation")
    elif uplift_v03 >= 0.001:
        good.append(f"neutral ER uplift {uplift_v03:.2%}")
    if uplift_v03 < 0.0005 and (n_up_v03 >= 3 or maxshock(v03_delta05) >= 0.10 or l1_v03 >= 0.4):
        suggestion = "FREEZE NEUTRAL_60_40"
    elif len(bad) >= 3:
        suggestion = "DO NOT FREEZE"
    elif len(good) >= 3 and len(bad) <= 1:
        suggestion = "FREEZE CORE_V0.3"
    else:
        suggestion = "DO NOT FREEZE"
    decision = {"suggested_option": suggestion, "good_signals": good, "bad_signals": bad,
                "median_sensitivity_reduction": med_red, "max_confidence_jump": max_conf_jump,
                "uplift_v03": uplift_v03}

    # ---- Export ----
    out = ensure_dir(ROOT / "outputs" / "latest")
    save_csv(pd.DataFrame({
        "asset_id": order9,
        "ticker": [tickers[a] for a in order9],
        "strategic_cma": [float(mu_cma9.loc[a]) for a in order9],
        "arith_diagnostic": [float(arith_diag.loc[a]) for a in order9],
        "vol_5y_primary": [float(vol5.loc[a]) for a in order9],
        "vol_3y_sensitivity": [float(vol3.loc[a]) for a in order9],
        "mdd_5y": [float(mdd5.loc[a]) for a in order9],
    }).set_index("asset_id"), out / "asset_summary.csv")
    save_csv(er_table.reset_index(names="asset_id"), out / "expected_returns.csv", index=False)
    save_csv(weekly_ret9, out / "weekly_returns_krw.csv")
    save_csv(cov5, out / "covariance_5y_primary.csv")
    save_csv(cov3, out / "covariance_3y_sensitivity.csv")
    save_csv(cov3, out / "covariance_3y.csv")
    save_csv(corr5, out / "correlation_5y_primary.csv")
    save_csv(corr3, out / "correlation_3y_sensitivity.csv")
    save_csv(corr3, out / "correlation_3y.csv")
    save_csv(corr5, out / "correlation_5y.csv")
    save_csv(frontier, out / "efficient_frontier.csv")
    # V0.2 frozen under legacy name + explicit alias; V0.3 is the new primary.
    save_csv(w_v02.rename("weight").to_frame(), out / "core_benchmark_weights.csv")
    save_csv(w_v02.rename("weight").to_frame(), out / "core_benchmark_v02_weights.csv")
    save_csv(w_v02.rename("weight").to_frame(), out / "core_v02_weights.csv")
    save_csv(w_v03.rename("weight").to_frame(), out / "core_v03_weights.csv")
    save_csv(w_neutral.rename("weight").to_frame(), out / "neutral_60_40_weights.csv")
    save_csv(w_tan9.rename("weight").to_frame(), out / "tangency_weights.csv")
    save_csv(pd.DataFrame({"equal_weight": w_eq9, "sixty_forty_legacy": w_6040_legacy}),
             out / "comparator_weights.csv")
    save_csv(sanity.reset_index(), out / "sanity_check_metrics.csv", index=False)
    save_csv(comp_df.reset_index(), out / "benchmark_comparison.csv", index=False)
    save_csv(pd.DataFrame([{"asset": a, "w_5y": float(w_v02.loc[a]),
                            "w_3y": float(w_v02_3y.loc[a]),
                            "diff": float(w_v02.loc[a] - w_v02_3y.loc[a])} for a in order10]),
             out / "risk_horizon_sensitivity.csv", index=False)
    save_csv(pd.DataFrame([{"asset": a, "w_5y": float(w_v03.loc[a]),
                            "w_3y": float(w_v03_3y.loc[a]),
                            "diff": float(w_v03.loc[a] - w_v03_3y.loc[a])} for a in order10]),
             out / "risk_horizon_sensitivity_v03.csv", index=False)
    save_csv(sens_df, out / "expected_return_sensitivity.csv", index=False)
    save_csv(red_df, out / "er_sensitivity_v02_vs_v03.csv", index=False)
    save_csv(summarize_bound_hits(w_v03, bounds), out / "bound_hit_diagnostics.csv", index=False)
    save_csv(conf_df, out / "bl_confidence_sensitivity.csv", index=False)
    save_csv(stab_df, out / "portfolio_stability_comparison.csv", index=False)
    save_csv(pd.DataFrame({
        "asset": order9,
        "strategic_cma": [float(mu_cma9.loc[a]) for a in order9],
        "prior_excess": [float(bl_primary["prior_excess"].loc[a]) for a in order9],
        "prior_abs": [float(prior9.loc[a]) for a in order9],
        "cma_excess_view": [float(bl_primary["Q"][i]) for i, a in enumerate(order9)],
        "posterior_excess": [float(bl_primary["posterior_excess"].loc[a]) for a in order9],
        "posterior_abs": [float(post9.loc[a]) for a in order9],
    }), out / "bl_prior_returns.csv", index=False)
    save_csv(pd.DataFrame({
        "asset": order9,
        "Q_excess": [float(bl_primary["Q"][i]) for i, a in enumerate(order9)],
        "omega": [float(bl_primary["omega"][i, i]) for i, a in enumerate(order9)],
        "tau": [tau] * len(order9),
        "confidence": [conf_primary] * len(order9),
    }), out / "bl_cma_views.csv", index=False)
    save_csv(pd.DataFrame({"asset": order9,
                           "posterior_abs": [float(post9.loc[a]) for a in order9]}),
             out / "bl_posterior_returns.csv", index=False)
    save_json({"target_volatility": ref_vol5, "reference_return": ref_ret,
               "covariance": "5Y Ledoit-Wolf primary", "cash_volatility": 0.0,
               "weights": {k: float(v) for k, v in w_neutral.items()}},
              out / "neutral_60_40_risk.json")
    save_json({
        "from": "CORE_V0.1", "to": "CORE_V0.3",
        "v02": "strategic CMA direct; hedged IEF/TIP; IEFA; 5Y primary + 3Y sensitivity; "
               "60/40-anchored max-return; cash optimizer variable",
        "v03": "V0.2 method preserved; optimizer ER replaced by BL posterior "
               "(neutral-implied prior, tau=0.05, CMA views at 25% confidence)",
    }, out / "methodology_changes.json")
    save_json({
        "model_version": "CORE_V0.3",
        "prior_method": "reverse_optimization_neutral_policy",
        "risk_free_rate": rf,
        "tau": tau,
        "primary_view_confidence": conf_primary,
        "confidence_grid": conf_grid,
        "view_type": "absolute_external_cma",
        "P": "identity",
        "primary_covariance": "5Y weekly Ledoit-Wolf",
        "risk_anchor": "neutral_60_40_volatility",
        "delta": bl_primary["delta"],
        "neutral_expected_return": ref_ret,
        "neutral_volatility": ref_vol5,
        "expected_return_model": "black_litterman_v0",
    }, out / "bl_methodology.json")
    save_json(decision, out / "benchmark_decision_metrics.json")

    xval_path = out / "cross_validation.json"
    xval_status = "NOT RUN"
    if xval_path.exists():
        try:
            import json as _j
            xval_status = _j.loads(xval_path.read_text()).get("status", "UNKNOWN")
        except Exception:
            xval_status = "UNKNOWN"
    meta = {
        "model_version": "CORE_V0.3",
        "expected_return_convention": cfg_opt.get("expected_return_convention"),
        "expected_return_model": "black_litterman_v0",
        "run_timestamp": t0.isoformat(),
        "data_mode": mode,
        "snapshot_dir": str(snap_dir.relative_to(ROOT)) if snap_dir.exists() else None,
        "risk_lookback_years_primary": look_p,
        "risk_lookback_years_sensitivity": look_s,
        "frequency": cfg_opt["risk"].get("frequency", "weekly"),
        "covariance_method": "ledoit_wolf",
        "covariance_impl": cov_w5.attrs.get("method", "unknown"),
        "risk_free_rate": rf,
        "data_start": data_start,
        "data_end": data_end,
        "tickers": tickers,
        "diagnostics": diag,
        "target_volatility": ref_vol5,
        "status": status,
        "check_issues": issues,
        "comparator_notes": comp_notes,
        "horizon_l1_v02": l1_v02,
        "horizon_l1_v03": l1_v03,
        "cross_validation": xval_status,
    }
    save_json(meta, out / "run_metadata.json")

    # ---- Plots ----
    mv_row = frontier.iloc[0]
    plot_frontier_v02(frontier, {"ret": float(mv_row.expected_return), "vol": float(mv_row.volatility)},
                      {"ret": t_ret, "vol": t_vol},
                      {"ret": ref_ret, "vol": ref_vol5},
                      {"ret": v02_ret, "vol": v02_vol}, out / "frontier_v02.png")
    plot_correlation(corr5, "5Y Primary Correlation (KRW weekly, Ledoit-Wolf)", out / "correlation_5y_primary.png")
    plot_correlation(corr3, "3Y Sensitivity Correlation (KRW weekly, Ledoit-Wolf)", out / "correlation_3y_sensitivity.png")
    plot_weights_compare(
        {"Core V0.2": w_v02, "Tangency": w_tan9, "Neutral 60/40": w_neutral},
        out / "weights_compare.png")
    plot_horizon_sensitivity(w_v02, w_v02_3y, out / "horizon_3y5y.png")
    plot_er_sensitivity(v02_delta05, out / "er_sensitivity.png")
    nav = {}
    for n, w in ports.items():
        frame = weekly_ret10 if set(w.index) == set(order10) else weekly_ret9
        nav[n] = (1.0 + portfolio_return_series(frame[[c for c in w.index]], w)).cumprod()
    nav["core_v03"] = (1.0 + portfolio_return_series(weekly_ret10, w_v03)).cumprod()
    plot_nav(pd.DataFrame(nav), out / "nav_comparison.png")
    plot_bl_er_compare(mu_cma9, prior9, post9, out / "bl_er_compare.png")
    plot_weights_v03(w_neutral, w_v02, w_v03, out / "weights_v03.png")
    plot_confidence_path(conf_df, out / "confidence_path.png")
    plot_sensitivity_compare(v02_delta05, v03_delta05, out / "sensitivity_compare.png")
    plot_horizon_sensitivity(w_v03, w_v03_3y, out / "horizon_v03_3y5y.png")

    # ---- Console ----
    print("\nCORE BENCHMARK V0.3 (BL posterior, c=25%)\n")
    print(f"Data: {data_start} ~ {data_end} ({len(weekly_ret9)} weekly, mode={mode})")
    print(f"Risk: {look_p}Y primary + {look_s}Y sensitivity Ledoit-Wolf ({cov_w5.attrs.get('method')})")
    print(f"BL: tau={tau}, confidence={conf_primary}, delta={bl_primary['delta']:.4f}\n")
    print(f"Neutral 60/40: ER={ref_ret:.3%} Vol={ref_vol5:.3%}\n")
    print("Core V0.3 Weights")
    for a in order10:
        print(f"  {a:16s} {float(w_v03.loc[a]):.4f}")
    print(f"\nV0.3 Expected Return: {v03_ret:.3%}  Vol: {v03_vol:.3%}  Sharpe: {v03_sh:.3f}")
    print(f"V0.2 Expected Return: {v02_ret:.3%}  Vol: {v02_vol:.3%}  Sharpe: {v02_sh:.3f}")
    print(f"\nHorizon L1: V0.2={l1_v02:.4f} V0.3={l1_v03:.4f}")
    print(f"Upper hits: V0.2={n_up_v02} V0.3={n_up_v03} | "
          f"Zero risky: V0.2={zero_v02['n_zero']} V0.3={zero_v03['n_zero']}")
    print(f"Median sensitivity reduction: "
          f"{med_red:.0%}" if med_red is not None else "Median sensitivity reduction: n/a")
    print(f"Suggested: {suggestion}")
    if issues:
        print("\nCHECKS:")
        for i in issues:
            print(f"  - {i}")
    if comp_notes:
        print("\nNOTES:")
        for nn in comp_notes:
            print(f"  - {nn}")
    print(f"\nSTATUS: {status}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
