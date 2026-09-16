"""Constrained portfolio optimization (no leverage/short).

Uses SLSQP via scipy when available, otherwise a deterministic
multi-start projected-gradient fallback (pure numpy). Never returns
infeasible weights silently: raises on failure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constraints import group_violation, project_box_simplex, random_feasible


def portfolio_stats(
    w: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float
) -> tuple[float, float, float]:
    w = np.asarray(w, dtype=float)
    ret = float(w @ mu)
    var = float(w @ cov @ w)
    vol = float(np.sqrt(max(var, 0.0)))
    sharpe = float((ret - rf) / vol) if vol > 1e-12 else float("nan")
    return ret, vol, sharpe


def _scipy_available() -> bool:
    try:
        import scipy.optimize  # noqa: F401

        return True
    except Exception:
        return False


def _pgd(
    obj_grad,
    w0: np.ndarray,
    lb: np.ndarray,
    ub: np.ndarray,
    order,
    groups: list[dict],
    group_penalty: float,
    max_iter: int,
    tol: float,
    init_step: float,
) -> np.ndarray:
    """Projected gradient descent with backtracking; group caps via penalty."""
    w = project_box_simplex(np.asarray(w0, dtype=float), lb, ub)

    def fg(wv):
        f, g = obj_grad(wv)
        viol, _ = group_violation(wv, order, groups)
        if viol > 0:
            idx = {a: k for k, a in enumerate(order)}
            f = f + group_penalty * viol**2
            g = np.asarray(g, dtype=float).copy()
            for grp in groups:
                tot = float(sum(wv[idx[a]] for a in grp["assets"]))
                v = tot - float(grp["max"])
                if v > 0:
                    for a in grp["assets"]:
                        g[idx[a]] += 2.0 * group_penalty * v
        return float(f), np.asarray(g, dtype=float)

    f_cur, g_cur = fg(w)
    step = init_step
    for _ in range(max_iter):
        # backtracking line search
        improved = False
        for _ls in range(25):
            w_new = project_box_simplex(w - step * g_cur, lb, ub)
            f_new, g_new = fg(w_new)
            if f_new < f_cur - 1e-12:
                improved = True
                break
            step *= 0.5
            if step < 1e-14:
                break
        if not improved:
            break
        if float(np.max(np.abs(w_new - w))) < tol:
            w = w_new
            break
        w = w_new
        f_cur, g_cur = f_new, g_new
        step = min(step * 1.5, init_step)
    return w


def _multi_start(
    obj_grad,
    lb: np.ndarray,
    ub: np.ndarray,
    order,
    groups: list[dict],
    cfg: dict,
    seed: int,
    init_step: float,
    score,
    n_start: int | None = None,
    warm: list | None = None,
    polish_kicks: int = 80,
    max_iter: int | None = None,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n_total = int(cfg.get("multi_start", 16)) if n_start is None else int(n_start)
    if max_iter is None:
        max_iter = int(cfg.get("max_iter", 3000))
    tol = float(cfg.get("tolerance", 1e-8))
    gp = float(cfg.get("group_penalty", 1e6))
    n = len(order)
    starts = [np.full(n, 1.0 / n)]
    if warm:
        starts.extend([np.asarray(x, dtype=float) for x in warm])
    for _ in range(max(n_total - len(starts), 0) + 1):
        starts.append(random_feasible(rng, lb, ub))
    best = None
    best_score = np.inf
    for s in starts:
        if s is None:
            continue
        w = _pgd(obj_grad, s, lb, ub, order, groups, gp, max_iter, tol, init_step)
        # polish with small random kicks
        for _ in range(int(polish_kicks)):
            kick = w + rng.normal(0, 0.01, size=n)
            wk = project_box_simplex(kick, lb, ub)
            if score(wk) < score(w):
                w = wk
        sc = score(w)
        viol, _ = group_violation(w, order, groups)
        sc_total = sc + gp * viol**2
        if sc_total < best_score:
            best_score = sc_total
            best = w
    if best is None:
        raise RuntimeError("Optimizer failed: no candidate produced")
    return best


def _scipy_solve(
    fun,
    jac,
    w0: np.ndarray,
    lb: np.ndarray,
    ub: np.ndarray,
    order,
    groups: list[dict],
) -> np.ndarray | None:
    try:
        import scipy.optimize as so
    except Exception:
        return None
    idx = {a: k for k, a in enumerate(order)}
    cons = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    for grp in groups:
        members = [idx[a] for a in grp["assets"]]
        cap = float(grp["max"])
        cons.append(
            {
                "type": "ineq",
                "fun": (lambda w, m=members, c=cap: float(c - sum(w[i] for i in m))),
            }
        )
    try:
        res = so.minimize(
            fun,
            np.asarray(w0, dtype=float),
            jac=jac,
            bounds=list(zip(lb.tolist(), ub.tolist())),
            constraints=cons,
            method="SLSQP",
            options={"maxiter": 1000, "ftol": 1e-12},
        )
    except Exception:
        return None
    if not res.success:
        return None
    w = project_box_simplex(np.asarray(res.x, dtype=float), lb, ub)
    return w


def _solve(
    base_obj_grad,
    score,
    lb,
    ub,
    order,
    groups,
    cfg,
    seed,
    init_step,
    scipy_obj=None,
):
    """Try scipy multi-start first (if installed), keep best vs PGD result."""
    rng = np.random.default_rng(seed)
    n = len(order)
    cands = []
    if _scipy_available() and scipy_obj is not None:
        fun, jac = scipy_obj
        for _ in range(int(cfg.get("multi_start", 16))):
            w0 = random_feasible(rng, lb, ub)
            w = _scipy_solve(fun, jac, w0, lb, ub, order, groups)
            if w is not None:
                cands.append(w)
    w_pgd = _multi_start(base_obj_grad, lb, ub, order, groups, cfg, seed, init_step, score)
    cands.append(w_pgd)
    gp = float(cfg.get("group_penalty", 1e6))
    best, best_sc = None, np.inf
    for w in cands:
        viol, _ = group_violation(w, order, groups)
        sc = score(w) + gp * viol**2
        if sc < best_sc:
            best_sc, best = sc, w
    if best is None:
        raise RuntimeError("Optimizer failed: no feasible candidate")
    return best


def min_variance(
    cov: pd.DataFrame, order, bounds_cfg, groups, cfg, seed: int = 42
) -> pd.Series:
    C = cov.loc[order, order].to_numpy(float)
    lb, ub = _bounds(order, bounds_cfg)
    L = 2.0 * float(np.max(np.linalg.eigvalsh(C))) + 1e-12
    step = 1.0 / max(L, 1e-12)

    def obj_grad(w):
        w = np.asarray(w, float)
        return float(w @ C @ w), 2.0 * (C @ w)

    def score(w):
        return float(np.asarray(w, float) @ C @ np.asarray(w, float))

    def s_fun(w):
        return float(np.asarray(w, float) @ C @ np.asarray(w, float))

    def s_jac(w):
        return 2.0 * (C @ np.asarray(w, float))

    w = _solve(obj_grad, score, lb, ub, order, groups, cfg, seed, step,
               scipy_obj=(s_fun, s_jac))
    return pd.Series(w, index=order)


def _solve_lambda_risk(
    m: np.ndarray,
    C: np.ndarray,
    lam: float,
    w_init: np.ndarray,
    lb: np.ndarray,
    ub: np.ndarray,
    order,
    groups: list[dict],
    gp: float,
    step: float,
    max_iter: int,
    tol: float,
    rng: np.random.Generator,
    polish: int = 10,
) -> np.ndarray:
    """Minimize w'Cw - lam*m'w over box-simplex (+ soft group caps)."""

    def obj_grad(w):
        w = np.asarray(w, float)
        return float(w @ C @ w - lam * (w @ m)), 2.0 * (C @ w) - lam * m

    w = _pgd(obj_grad, w_init, lb, ub, order, groups, gp, max_iter, tol, step)
    base = float(w @ C @ w - lam * (w @ m))

    def full_obj(x):
        x = np.asarray(x, float)
        viol, _ = group_violation(x, order, groups)
        return float(x @ C @ x - lam * (x @ m) + gp * viol**2)

    for _ in range(int(polish)):
        wk = project_box_simplex(w + rng.normal(0, 0.005, size=len(order)), lb, ub)
        if full_obj(wk) < base:
            w, base = wk, full_obj(wk)
    return w


def min_variance_with_target(
    mu: pd.Series,
    cov: pd.DataFrame,
    target: float,
    order,
    bounds_cfg,
    groups,
    cfg,
    seed: int = 42,
    warm: list | None = None,
    n_start: int | None = None,
    polish_kicks: int = 80,
    max_iter: int | None = None,
) -> pd.Series:
    """Min-variance portfolio with m'w = target, via Lagrangian dual bisection.

    For fixed lam, min w'Cw - lam*m'w is smooth and well-conditioned, so PGD
    converges reliably; ret(w(lam)) increases monotonically in lam, hence we
    bisect lam to hit the target. Falls back to the penalty formulation if
    bisection cannot close the gap.
    """
    m = mu.loc[order].to_numpy(float)
    C = cov.loc[order, order].to_numpy(float)
    lb, ub = _bounds(order, bounds_cfg)
    L = 2.0 * float(np.max(np.linalg.eigvalsh(C))) + 1e-12
    step = 1.0 / max(L, 1e-12)
    gp = float(cfg.get("group_penalty", 1e6))
    tol = float(cfg.get("tolerance", 1e-8))
    inner_iter = int(max_iter) if max_iter is not None else 400
    rng = np.random.default_rng(seed)
    n = len(order)

    def ret_of(w):
        return float(np.asarray(w, float) @ m)

    def var_of(w):
        w = np.asarray(w, float)
        return float(w @ C @ w)

    inits = [np.full(n, 1.0 / n)]
    if warm:
        inits.extend([np.asarray(x, dtype=float) for x in warm])
    rng2 = np.random.default_rng(seed + 999)
    for _ in range(3):
        inits.append(random_feasible(rng2, lb, ub))

    def solve_lam(lam, w_init, iters):
        return _solve_lambda_risk(m, C, lam, w_init, lb, ub, order, groups,
                                  gp, step, iters, tol, rng, polish=10)

    # lam = 0 endpoint = min variance.
    cands = [(solve_lam(0.0, w0, inner_iter), 0.0) for w0 in inits]
    w_lo = min(cands, key=lambda t: var_of(t[0]) + gp * group_violation(t[0], order, groups)[0] ** 2)[0]
    r_lo = ret_of(w_lo)
    if abs(r_lo - target) <= 5e-5:
        return pd.Series(w_lo, index=order)

    if r_lo > target:
        # Target below achievable minimum (should not happen on the grid).
        raise RuntimeError(f"Target {target} below min-variance return {r_lo}")

    # Bracket: double lam until return exceeds target.
    lam_hi = 1.0
    w_hi = w_lo
    for _ in range(25):
        w_hi = solve_lam(lam_hi, w_hi, inner_iter)
        if ret_of(w_hi) >= target:
            break
        lam_hi *= 2.0
    else:
        raise RuntimeError(f"Target {target} unreachable (lam bracket failed)")
    lam_lo = 0.0
    best, best_key = w_lo, (abs(r_lo - target), var_of(w_lo))
    if abs(ret_of(w_hi) - target) < best_key[0]:
        best, best_key = w_hi, (abs(ret_of(w_hi) - target), var_of(w_hi))

    w_cur = w_hi
    for _ in range(30):
        lam_mid = 0.5 * (lam_lo + lam_hi)
        w_cur = solve_lam(lam_mid, w_cur, inner_iter)
        r_mid = ret_of(w_cur)
        key = (abs(r_mid - target), var_of(w_cur))
        if key < best_key:
            best_key, best = key, w_cur
        if abs(r_mid - target) <= 1e-6:
            break
        if r_mid < target:
            lam_lo = lam_mid
        else:
            lam_hi = lam_mid

    if best_key[0] > 5e-4:
        # Fallback: penalty formulation with correctly scaled step.
        rho = 1e6
        eff_L = L + 2.0 * rho * float(m @ m)
        step_p = 1.0 / max(eff_L, 1e-12)

        def obj_grad(w, _m=m, _C=C, _t=target, _rho=rho):
            w = np.asarray(w, float)
            gap = float(w @ _m - _t)
            return float(w @ _C @ w + _rho * gap**2), 2.0 * (_C @ w) + 2.0 * _rho * gap * _m

        def score(w, _m=m, _C=C, _t=target):
            w = np.asarray(w, float)
            return float(w @ _C @ w + 1e7 * (float(w @ _m - _t)) ** 2)

        w_fb = _multi_start(obj_grad, lb, ub, order, groups, cfg, seed,
                            step_p, score, n_start=n_start, warm=[best, w_lo, w_hi],
                            polish_kicks=polish_kicks, max_iter=3000)
        key_fb = (abs(ret_of(w_fb) - target), var_of(w_fb))
        if key_fb < best_key:
            best_key, best = key_fb, w_fb
    if best_key[0] > 5e-4:
        raise RuntimeError(f"Target-vol optimization failed for target={target} (gap={best_key[0]})")
    return pd.Series(best, index=order)


def max_return_greedy(
    mu: pd.Series, order, bounds_cfg, groups, cfg: dict | None = None, seed: int = 42
) -> pd.Series:
    """Exact greedy LP + PGD polish; returns max-return feasible weights."""
    m = {a: float(mu.loc[a]) for a in order}
    lb = {a: float(bounds_cfg[a]["min"]) for a in order}
    ub = {a: float(bounds_cfg[a]["max"]) for a in order}
    w = {a: lb[a] for a in order}
    remaining = 1.0 - sum(w.values())
    head = {g["name"]: float(g["max"]) - sum(w[a] for a in g["assets"]) for g in groups}
    member_of = {a: [] for a in order}
    for g in groups:
        for a in g["assets"]:
            member_of[a].append(g["name"])
    for a in sorted(order, key=lambda x: m[x], reverse=True):
        if remaining <= 1e-12:
            break
        cap = ub[a] - w[a]
        for gname in member_of[a]:
            cap = min(cap, head[gname])
        cap = min(cap, remaining)
        if cap > 0:
            w[a] += cap
            remaining -= cap
            for gname in member_of[a]:
                head[gname] -= cap
    if remaining > 1e-9:
        raise RuntimeError("Max-return LP infeasible under group caps")
    greedy = pd.Series([w[a] for a in order], index=order)
    if cfg is None:
        return greedy
    # Polish with PGD on linear objective; keep the better.
    C0 = np.eye(len(order)) * 1e-12
    mv = np.array([m[a] for a in order])

    def obj_grad(x):
        x = np.asarray(x, float)
        return float(-x @ mv), -mv

    def score(x):
        return float(-np.asarray(x, float) @ mv)

    from .constraints import get_bounds as _gb

    lbv, ubv = _gb(order, bounds_cfg)
    w2 = _multi_start(obj_grad, lbv, ubv, order, groups, cfg, seed, 0.1, score)
    if score(w2) < score(greedy.to_numpy(float)) - 1e-12:
        return pd.Series(w2, index=order)
    return greedy


def max_sharpe(
    mu: pd.Series,
    cov: pd.DataFrame,
    rf: float,
    order,
    bounds_cfg,
    groups,
    cfg,
    seed: int = 42,
) -> pd.Series:
    m = mu.loc[order].to_numpy(float)
    C = cov.loc[order, order].to_numpy(float)
    lb, ub = _bounds(order, bounds_cfg)

    def obj_grad(w):
        w = np.asarray(w, float)
        ret = float(w @ m)
        vol = float(np.sqrt(max(w @ C @ w, 1e-18)))
        excess = ret - rf
        sharpe = excess / vol
        grad = -(m * vol - excess * (C @ w) / vol) / (vol**2)
        return float(-sharpe), np.asarray(grad, float)

    def score(w):
        w = np.asarray(w, float)
        vol = float(np.sqrt(max(w @ C @ w, 1e-18)))
        return float(-(float(w @ m) - rf) / vol)

    def s_fun(w):
        return score(w)

    def s_jac(w):
        _, g = obj_grad(w)
        return np.asarray(g, float)

    w = _solve(obj_grad, score, lb, ub, order, groups, cfg, seed + 7, 0.5,
               scipy_obj=(s_fun, s_jac))
    _, vol, sh = portfolio_stats(w, m, C, rf)
    if not np.isfinite(sh):
        raise RuntimeError("Max-Sharpe solution has non-finite Sharpe")
    return pd.Series(np.asarray(w, float), index=order)


def _solve_gamma_ret(
    m: np.ndarray,
    C: np.ndarray,
    gamma: float,
    w_init: np.ndarray,
    lb: np.ndarray,
    ub: np.ndarray,
    order,
    groups: list[dict],
    gp: float,
    lmax: float,
    max_iter: int,
    tol: float,
    rng: np.random.Generator,
    polish: int = 10,
    step_cap: float = 5.0,
) -> np.ndarray:
    """Minimize -m'w + gamma*w'Cw over box-simplex (+ soft group caps)."""
    raw_step = 1.0 / max(2.0 * gamma * lmax, 1e-12)
    step = min(raw_step, step_cap)

    def obj_grad(w):
        w = np.asarray(w, float)
        return float(-(w @ m) + gamma * (w @ C @ w)), -m + 2.0 * gamma * (C @ w)

    w = _pgd(obj_grad, w_init, lb, ub, order, groups, gp, max_iter, tol, step)

    def full_obj(x):
        x = np.asarray(x, float)
        viol, _ = group_violation(x, order, groups)
        return float(-(x @ m) + gamma * (x @ C @ x) + gp * viol**2)

    base = full_obj(w)
    for _ in range(int(polish)):
        wk = project_box_simplex(w + rng.normal(0, 0.005, size=len(order)), lb, ub)
        fk = full_obj(wk)
        if fk < base:
            w, base = wk, fk
    return w


def max_return_with_vol_cap(
    mu: pd.Series,
    cov: pd.DataFrame,
    target_vol: float,
    order,
    bounds_cfg,
    groups,
    cfg,
    seed: int = 42,
    warm: list | None = None,
    max_iter: int = 400,
) -> pd.Series:
    """Maximize m'w s.t. vol(w) <= target_vol (+ box/simplex/group caps).

    Solved by bisection on the risk-aversion gamma of min -m'w + gamma*w'Cw:
    vol(w(gamma)) decreases monotonically in gamma. Works with a cash sleeve
    (zero vol/return leg) included in `order`.
    """
    m = mu.loc[order].to_numpy(float)
    C = cov.loc[order, order].to_numpy(float)
    lb, ub = _bounds(order, bounds_cfg)
    lmax = float(np.max(np.linalg.eigvalsh(C)))
    gp = float(cfg.get("group_penalty", 1e6))
    tol = float(cfg.get("tolerance", 1e-8))
    rng = np.random.default_rng(seed)
    n = len(order)

    def ret_of(w):
        return float(np.asarray(w, float) @ m)

    def vol_of(w):
        w = np.asarray(w, float)
        return float(np.sqrt(max(w @ C @ w, 0.0)))

    w_corner = max_return_greedy(mu, order, bounds_cfg, groups, None, seed).to_numpy(float)
    if vol_of(w_corner) <= target_vol + 1e-9:
        return pd.Series(w_corner, index=order)  # cap does not bind

    inits = [w_corner, np.full(n, 1.0 / n)]
    if warm:
        inits.extend([np.asarray(x, dtype=float) for x in warm])

    def gamma_obj(w, gamma):
        w = np.asarray(w, float)
        viol, _ = group_violation(w, order, groups)
        return float(-(w @ m) + gamma * (w @ C @ w) + gp * viol**2)

    def solve_gamma(gamma, w_main, iters):
        # Multi-start: PGD stalls at vertices, so never trust a single chain.
        cands = [w_main, np.full(n, 1.0 / n),
                 random_feasible(rng, lb, ub), random_feasible(rng, lb, ub)]
        best_g, best_f = None, np.inf
        for s in cands:
            w = _solve_gamma_ret(m, C, gamma, s, lb, ub, order, groups,
                                 gp, lmax, iters, tol, rng)
            f = gamma_obj(w, gamma)
            if f < best_f:
                best_g, best_f = w, f
        return best_g

    gamma_hi = 1.0
    w_hi = w_corner
    for _ in range(25):
        w_hi = solve_gamma(gamma_hi, w_hi, 150)
        if vol_of(w_hi) <= target_vol:
            break
        gamma_hi *= 2.0
    else:
        raise RuntimeError("Vol-cap bracket failed (target below min variance?)")
    w_floor = min_variance(cov, order, bounds_cfg, groups, cfg, seed=seed).to_numpy(float)
    if vol_of(w_floor) > target_vol + 1e-9:
        raise RuntimeError(
            f"Infeasible: min-variance vol {vol_of(w_floor):.4f} > target {target_vol:.4f}"
        )

    # Light bisection for bracketing (approximate solves are sufficient here).
    gamma_lo = 0.0
    w_cur = w_hi
    for _ in range(25):
        gamma_mid = 0.5 * (gamma_lo + gamma_hi)
        w_cur = solve_gamma(gamma_mid, w_cur, 150)
        if vol_of(w_cur) <= target_vol:
            gamma_hi = gamma_mid
        else:
            gamma_lo = gamma_mid

    # Focused refinement around the binding gamma: scan neighbors with
    # multi-start thorough solves, then keep max return among feasible.
    rng_ref = np.random.default_rng(seed + 7919)
    pool = [w_corner, w_floor, w_cur]
    for g in {gamma_hi * f for f in (0.9, 0.95, 1.0, 1.05, 1.1)}:
        starts = [w_cur] + [random_feasible(rng_ref, lb, ub) for _ in range(2)]
        for s in starts:
            pool.append(_solve_gamma_ret(m, C, g, s, lb, ub, order, groups,
                                         gp, lmax, max_iter, tol, rng_ref, polish=20))
    best, best_ret = None, -np.inf
    for w0 in inits + pool:
        w0 = np.asarray(w0, float)
        if vol_of(w0) <= target_vol + 1e-9 and ret_of(w0) > best_ret:
            best, best_ret = w0, ret_of(w0)
    if best is None:
        raise RuntimeError("Vol-capped max-return optimization failed")
    return pd.Series(np.asarray(best, float), index=order)


def _bounds(order, bounds_cfg):
    from .constraints import get_bounds

    return get_bounds(order, bounds_cfg)
