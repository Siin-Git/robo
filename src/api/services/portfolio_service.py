"""Portfolio application service (no financial math here).

Volatility/TE come from the existing risk convention (5Y weekly Ledoit-Wolf
over the price store); sleeve construction rules live in
``src.forward.portfolio`` and are NOT reimplemented.
"""
from __future__ import annotations

import pandas as pd

from ...forward.prices import CORE_IDS, theme_asset_id
from ...risk.covariance import annualize_covariance, ledoit_wolf_covariance
from ...db.repositories.forward import PriceRepository, TargetRepository, ThemeRepository
from ..errors import ApiError, not_found
from . import _common as C


def _cfg():
    return C.load_forward_cfg()["forward_test"]


def _tickers(session) -> dict:
    return {t.theme_id: t.ticker for t in ThemeRepository(session).list(active=None)}


def _legs(weights: dict, tickers: dict) -> list[dict]:
    out = []
    for aid, w in weights.items():
        if aid == "cash":
            out.append({"asset_id": aid, "weight": float(w), "asset_type": "cash",
                        "ticker": None})
        elif aid.startswith("theme:"):
            tid = aid.split(":", 1)[1]
            out.append({"asset_id": tid, "weight": float(w), "asset_type": "theme",
                        "ticker": tickers.get(tid)})
        else:
            out.append({"asset_id": aid, "weight": float(w), "asset_type": "core",
                        "ticker": None})
    return out


def core(session) -> dict:
    frozen_w, meta = C.frozen_bundle()
    return {"benchmark_version": _cfg()["benchmark_version"],
            "model_date": (meta.get("run_timestamp", "") or "")[:10],
            "snapshot_date": meta.get("data_end"),
            "weights": _legs(frozen_w, _tickers(session))}


def _cov_asof(session, asset_ids: list[str], asof, weeks: int = 260):
    from . import market_comparison
    if market_comparison.enabled():
        return market_comparison.risk_cov(asset_ids, asof, weeks)
    frames = {}
    for aid in asset_ids:
        rows = PriceRepository(session).series(aid, end=asof)
        if not rows:
            return None
        s = pd.Series([float(p) for _, p in rows],
                      index=pd.to_datetime([d for d, _ in rows]))
        frames[aid] = s
    levels = pd.DataFrame(frames).sort_index()
    levels = levels[levels.index.dayofweek < 5]
    weekly = levels.resample("W-FRI").last().pct_change().dropna(how="any")
    if len(weekly) < weeks:
        return None
    window = weekly.iloc[-weeks:]
    return annualize_covariance(ledoit_wolf_covariance(window), 52)


def _base_weights_for(session, participant_id: str, user_id: str | None = None) -> tuple[dict, str]:
    """Return (base_weights, mode). Prefers user-selected frontier base if exists."""
    if user_id:
        from ...db.models.base_selection import BasePortfolioSelection as _BPS
        from sqlalchemy import select
        row = session.scalars(select(_BPS).where(
            _BPS.user_id == user_id, _BPS.status == "active").order_by(_BPS.selected_at.desc())).first()
        if row is not None:
            return dict(row.weights_json), "user_selected"
    frozen_w, _ = C.frozen_bundle()
    return dict(frozen_w), "benchmark_test"


def personalized(session, participant_id: str, user_id: str | None = None) -> dict:
    from ...db.models.account import Account as _A
    from sqlalchemy import select
    acc = session.scalars(select(_A).where(
        _A.participant_id == participant_id, _A.account_type == "personal")).first()
    if acc is None:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")
    tgt = TargetRepository(session).latest(acc.account_id)
    if tgt is None:
        raise ApiError("PORTFOLIO_NOT_READY", "No personalized target yet.", 409)
    weights = dict(tgt.weights_json)
    # If user has selected a base, the theme tilt should have been funded from that base.
    # For display, we still show the actual personalized weights, but also expose mode.
    base_w, mode = _base_weights_for(session, participant_id, user_id)
    asof = C.as_date(tgt.effective_date)
    vol = te = base_vol = None
    risk_date = C.latest_price_date(session)
    from . import market_comparison
    if market_comparison.enabled():
        risk_date = market_comparison.price_date()
    try:
        asset_ids = list(dict.fromkeys(a for a in [*base_w, *weights] if a != "cash"))
        cov = _cov_asof(session, asset_ids, risk_date) if risk_date else None
        if cov is not None:
            import numpy as np
            cols = [c for c in weights if c in cov.index]
            v = np.array([weights[c] for c in cols], float)
            vol = float((v @ cov.loc[cols, cols].to_numpy(float) @ v) ** 0.5)
            b = np.array([base_w.get(c, 0.0) for c in cov.index], float)
            base_vol = float((b @ cov.to_numpy(float) @ b) ** 0.5)
            frozen_w, _ = C.frozen_bundle()
            dall = sorted(set(weights) | set(frozen_w))
            d = np.array([weights.get(c, 0.0) - frozen_w.get(c, 0.0) for c in dall
                          if c in cov.index], float)
            cols2 = [c for c in dall if c in cov.index]
            te = float((d @ cov.loc[cols2, cols2].to_numpy(float) @ d) ** 0.5)
    except Exception:
        vol = te = base_vol = None
    return {"participant_id": participant_id, "as_of": asof,
            "benchmark_version": _cfg()["benchmark_version"],
            "expected_volatility": vol, "tracking_error": te,
            "risk_comparison": {"base_volatility": base_vol,
                                "personalized_volatility": vol,
                                "as_of": risk_date.isoformat() if risk_date else None,
                                "method": "5Y weekly Ledoit-Wolf" if base_vol is not None else None},
            "weights": _legs(weights, _tickers(session))}


def comparison(session, participant_id: str) -> dict:
    from ...db.models.account import Account as _A
    from sqlalchemy import select
    frozen_w, _ = C.frozen_bundle()
    acc = session.scalars(select(_A).where(
        _A.participant_id == participant_id, _A.account_type == "personal")).first()
    if acc is None:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")
    tgt = TargetRepository(session).latest(acc.account_id)
    if tgt is None:
        raise ApiError("PORTFOLIO_NOT_READY", "No personalized target yet.", 409)
    pw = {k: float(v) for k, v in dict(tgt.weights_json).items()}
    diff = {}
    for aid in sorted(set(frozen_w) | set(pw)):
        d = pw.get(aid, 0.0) - frozen_w.get(aid, 0.0)
        if abs(d) > 1e-12:
            disp = aid.split(":", 1)[1] if aid.startswith("theme:") else aid
            diff[disp] = d
    tickers = _tickers(session)
    person = personalized(session, participant_id)
    return {"core": _legs(frozen_w, tickers), "personalized": person["weights"],
            "active": [{"asset_id": k, "weight": float(v), "asset_type": "active",
                        "ticker": tickers.get(k)} for k, v in diff.items()]}


def themes_for(asset_ids: list[str]) -> list[str]:
    return [a for a in asset_ids if a.startswith("theme:")]


def summary(session, participant_id: str, user_id: str | None = None) -> dict:
    """Dashboard summary: base + personalized + themes + comparison + groups."""
    from ...db.models.account import Account as _A
    from sqlalchemy import select
    # Base
    base_w, base_mode = _base_weights_for(session, participant_id, user_id)
    # Find base selection details if exists
    base_sel = None
    if user_id:
        from ...db.models.base_selection import BasePortfolioSelection as _BPS
        base_sel = session.scalars(select(_BPS).where(
            _BPS.user_id == user_id, _BPS.status == "active").order_by(_BPS.selected_at.desc())).first()
    # Personalized
    risk_comparison = None
    try:
        pers = personalized(session, participant_id, user_id)
        pers_w = {w["asset_id"]: w["weight"] for w in pers["weights"]}
        pers_vol = pers.get("expected_volatility")
        pers_te = pers.get("tracking_error")
        risk_comparison = pers.get("risk_comparison")
    except Exception:
        pers_w = dict(base_w)
        pers_vol = None
        pers_te = None
    # Groups
    CORE_ALL = {"us_equity", "developed_ex_us", "emerging_markets", "korea_equity", "us_treasury", "korea_treasury", "tips", "gold", "global_reit", "cash"}
    def groups_for(weights: dict) -> dict:
        eq = sum(weights.get(a, 0) for a in ["us_equity", "developed_ex_us", "emerging_markets", "korea_equity"])
        fi = sum(weights.get(a, 0) for a in ["us_treasury", "korea_treasury", "tips"])
        alt = sum(weights.get(a, 0) for a in ["gold", "global_reit"])
        cash = weights.get("cash", 0)
        themes_sum = sum(v for k, v in weights.items() if k not in CORE_ALL)
        broad_eq = float(eq)
        return {
            "equity": float(eq), "fixed_income": float(fi), "alternatives": float(alt), "cash": float(cash),
            "broad_equity": float(broad_eq), "themes": float(themes_sum),
        }
    base_groups = groups_for(base_w)
    pers_groups = groups_for(pers_w)
    tickers = _tickers(session)
    # Themes: keys not in CORE_ALL are themes (supports both "theme:ai" and "ai")
    def _is_theme_key(k: str) -> bool:
        return k not in CORE_ALL
    theme_ids = [k for k in pers_w if _is_theme_key(k)]
    if not theme_ids:
        theme_ids = [k for k in base_w if _is_theme_key(k)]
    themes = []
    for tid in theme_ids:
        raw = tid.split(":", 1)[1] if ":" in tid else tid
        # pers_w uses stripped keys ("ai"), base_w uses raw core keys; handle both
        w = pers_w.get(tid)
        if w is None:
            w = pers_w.get(raw)
        if w is None:
            w = base_w.get(tid, base_w.get(raw, 0))
        # also handle prefixed lookup for themes stored with prefix
        if w is None and f"theme:{raw}" in pers_w:
            w = pers_w[f"theme:{raw}"]
        themes.append({"theme_id": raw, "display_name": raw, "ticker": tickers.get(raw), "weight": float(w or 0)})
    base_info = {
        "frontier_id": getattr(base_sel, "frontier_id", None),
        "expected_return": float(getattr(base_sel, "expected_return", 0)) if base_sel else None,
        "volatility": float(getattr(base_sel, "volatility", 0)) if base_sel else None,
        "weights": _legs(base_w, tickers),
        "groups": base_groups,
    }
    pers_info = {
        "volatility": pers_vol,
        "tracking_error": pers_te,
        "weights": _legs(pers_w, tickers),
        "groups": pers_groups,
    }
    # Comparison: base vs personalized for dashboard (not core vs personalized)
    active = []
    for aid in sorted(set(base_w) | set(pers_w)):
        d = pers_w.get(aid, 0) - base_w.get(aid, 0)
        if abs(d) > 1e-9:
            disp = aid.split(":", 1)[1] if aid.startswith("theme:") else aid
            active.append({"asset_id": disp, "weight": float(d), "asset_type": "active", "ticker": tickers.get(disp)})
    # Also keep core comparison for legacy
    try:
        comp_core = comparison(session, participant_id)
    except Exception:
        comp_core = {"active": []}
    return {
        "base": base_info,
        "personalized": pers_info,
        "themes": themes,
        "comparison": active,
        "core_comparison": comp_core.get("active", []),
        "portfolio_mode": base_mode,
        "risk_comparison": risk_comparison,
    }
