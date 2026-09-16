"""Personalized portfolio construction: equity-funded active sleeve + guardrail."""
from __future__ import annotations

import numpy as np
import pandas as pd

EQUITY_IDS = ["us_equity", "developed_ex_us", "emerging_markets", "korea_equity"]


def theme_target_weights(theme_ids: list[str], cfg: dict) -> dict[str, float]:
    sl = cfg["forward_test"]["active_sleeve"]
    tids = list(theme_ids)
    if len(tids) > int(sl["max_themes"]):
        raise ValueError(f"at most {sl['max_themes']} themes")
    if len(tids) == 1:
        w = {tids[0]: float(sl["one_theme_default_weight"])}
    elif len(tids) == 2:
        w = {t: float(sl["two_theme_default_weight_each"]) for t in tids}
    elif len(tids) == 0:
        return {}
    else:
        raise ValueError("V0 supports at most 2 themes")
    if any(v > float(sl["max_single_theme_weight"]) + 1e-12 for v in w.values()):
        raise ValueError("single theme weight exceeds max")
    if sum(w.values()) > float(sl["max_total_weight"]) + 1e-12:
        raise ValueError("total active weight exceeds max")
    return w


def fund_from_equities(core_w: dict, theme_w: dict[str, float],
                       region_map: dict[str, dict[str, float]] | None = None) -> tuple[dict, dict]:
    """Reduce ONLY equity sleeve to fund themes. Returns (new_core_equity_w, funding)."""
    core = dict(core_w)
    eq_total = sum(core[a] for a in EQUITY_IDS)
    total_theme = sum(theme_w.values())
    if total_theme > eq_total + 1e-12:
        raise ValueError("active sleeve larger than equity sleeve")
    funding = {a: 0.0 for a in EQUITY_IDS}
    for theme, t in theme_w.items():
        alloc = dict(region_map.get(theme, {})) if region_map else {}
        if alloc:
            s = sum(alloc.values())
            alloc = {a: v / s for a, v in alloc.items()}
            # cap by availability, spill remainder proportionally
            remainder, avail = t, {a: core[a] - funding[a] for a in EQUITY_IDS}
            for a, frac in alloc.items():
                take = min(t * frac, avail[a])
                funding[a] += take
                remainder -= take
            if remainder > 1e-12:
                pool = sum(max(avail[a] - funding[a] + 0, 0) for a in EQUITY_IDS)
                for a in EQUITY_IDS:
                    room = max(avail[a] - funding[a], 0.0)
                    funding[a] += remainder * (room / pool if pool > 0 else 0.0)
        else:
            for a in EQUITY_IDS:
                funding[a] += t * (core[a] / eq_total if eq_total > 0 else 0.0)
    new_core = dict(core)
    for a in EQUITY_IDS:
        new_core[a] -= funding[a]
        if new_core[a] < -1e-9:
            raise ValueError(f"equity funding overdraws {a}")
        new_core[a] = max(new_core[a], 0.0)
    return new_core, funding


def _vol(w: dict, cov: pd.DataFrame) -> float:
    cols = list(w)
    v = np.array([w[c] for c in cols], float)
    C = cov.loc[cols, cols].to_numpy(float)
    return float(np.sqrt(max(v @ C @ v, 0.0)))


def build_personalized(core_w: dict, theme_ids: list[str], cfg: dict,
                       cov_ext: pd.DataFrame,
                       region_map: dict | None = None) -> dict:
    """Assemble personalized weights (with cash leg) + TE/vol/guardrail report."""
    ft = cfg["forward_test"]
    sl = ft["active_sleeve"]
    theme_w = theme_target_weights(theme_ids, cfg)
    if not theme_w:
        w = dict(core_w)
        v = _vol({k: w[k] for k in w if k in cov_ext.index}, cov_ext)
        return {"weights": w, "theme_weights": {}, "funding": {},
                "vol": v, "core_vol": v, "te": 0.0, "scaled": False, "scale": 1.0}
    base_core, funding = fund_from_equities(core_w, theme_w, region_map)

    def assemble(scale: float) -> dict:
        w = dict(base_core)
        tw = {}
        for t, tv in theme_w.items():
            tw[t] = tv * scale
        giveback = (1.0 - scale) * sum(theme_w.values())
        # give back proportionally to what was taken
        taken = sum(funding.values())
        for a in EQUITY_IDS:
            w[a] += giveback * (funding[a] / taken if taken > 0 else 0.0)
        for t, tv in tw.items():
            w[t] = w.get(t, 0.0) + tv
        return w

    core_vol = _vol({k: core_w[k] for k in core_w if k in cov_ext.index}, cov_ext)
    limit = core_vol + float(ft["risk_guardrail"]["max_vol_increase_pp"]) / 100.0
    w = assemble(1.0)
    vol = _vol({k: w[k] for k in w if k in cov_ext.index}, cov_ext)
    scale, scaled = 1.0, False
    if vol > limit:
        scaled = True
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            if _vol({k: assemble(mid)[k] for k in assemble(mid) if k in cov_ext.index}, cov_ext) <= limit:
                lo = mid
            else:
                hi = mid
        scale = lo
        w = assemble(scale)
        vol = _vol({k: w[k] for k in w if k in cov_ext.index}, cov_ext)
        if vol > limit + 1e-9:
            raise RuntimeError("risk guardrail could not be satisfied by scaling")
    # TE vs core
    dall = sorted(set(w) | set(core_w))
    d = np.array([w.get(c, 0.0) - core_w.get(c, 0.0) for c in dall], float)
    cols = [c for c in dall if c in cov_ext.index]
    dd = np.array([w.get(c, 0.0) - core_w.get(c, 0.0) for c in cols], float)
    te = float(np.sqrt(max(dd @ cov_ext.loc[cols, cols].to_numpy(float) @ dd, 0.0)))
    validate_targets(w, cfg)
    return {"weights": w, "theme_weights": {t: v * scale for t, v in theme_w.items()},
            "funding": funding, "vol": vol, "core_vol": core_vol, "te": te,
            "scaled": scaled, "scale": scale}


def validate_targets(w: dict, cfg: dict) -> None:
    sl = cfg["forward_test"]["active_sleeve"]
    vals = np.array(list(w.values()), float)
    if np.isnan(vals).any() or np.isinf(vals).any():
        raise ValueError("target weights contain NaN/Inf")
    if abs(vals.sum() - 1.0) > 1e-6:
        raise ValueError(f"target weights sum to {vals.sum()}")
    if (vals < -1e-9).any():
        raise ValueError("negative target weight")
    theme_total = sum(v for k, v in w.items() if k.startswith("theme:"))
    if theme_total > float(sl["max_total_weight"]) + 1e-9:
        raise ValueError("active sleeve exceeds max")
