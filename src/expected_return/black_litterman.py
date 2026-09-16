"""Black-Litterman expected-return stabilization (V0.3).

Prior: reverse optimization from the Neutral policy portfolio.
Views: absolute external strategic CMA views (P = identity).
Uncertainty: Idzorek-style diagonal Omega scaled by (1-c)/c.
Numerics: solve-based, never explicit matrix inverse.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_delta(neutral_expected_return: float, neutral_volatility: float,
                  risk_free_rate: float) -> float:
    """delta = (E[R_neutral] - rf) / sigma_neutral^2."""
    var = float(neutral_volatility) ** 2
    if var <= 0:
        raise ValueError("neutral variance must be positive")
    return (float(neutral_expected_return) - float(risk_free_rate)) / var


def implied_equilibrium_returns(covariance: pd.DataFrame, risky_weights: pd.Series,
                                risk_aversion: float) -> pd.Series:
    """pi = delta * Sigma * w_risky (excess returns). No cash leg included."""
    C = covariance.loc[risky_weights.index, risky_weights.index].to_numpy(float)
    w = risky_weights.to_numpy(float)
    pi = float(risk_aversion) * (C @ w)
    return pd.Series(pi, index=risky_weights.index)


def build_cma_views(strategic_er: pd.Series, risk_free_rate: float,
                    order) -> tuple[np.ndarray, np.ndarray]:
    """Absolute CMA views in excess form: P = I, Q = CMA - rf."""
    order = list(order)
    P = np.eye(len(order))
    Q = np.array([float(strategic_er.loc[a]) - float(risk_free_rate) for a in order])
    return P, Q


def build_view_uncertainty(covariance: pd.DataFrame, P: np.ndarray, tau: float,
                           confidence: float) -> np.ndarray:
    """Omega_ii = ((1-c)/c) * tau * (P Sigma P')_ii (Idzorek-style, diagonal)."""
    c = float(confidence)
    if c < 0 or c > 1:
        raise ValueError("confidence must be in [0, 1]")
    C = covariance.to_numpy(float)
    diag = np.diag(P @ C @ P.T)
    if c <= 0.0:
        return np.diag(np.full_like(diag, np.inf))
    if c >= 1.0 - 1e-12:
        return np.diag(np.full_like(diag, 1e-12))
    scale = ((1.0 - c) / max(c, 1e-12)) * float(tau)
    return np.diag(scale * diag)


def black_litterman_posterior(prior_excess: pd.Series, covariance: pd.DataFrame,
                              P: np.ndarray, Q: np.ndarray, omega: np.ndarray,
                              tau: float, confidence: float | None = None) -> pd.Series:
    """mu_BL_excess = pi + tau*Sigma*P' * solve(P*tau*Sigma*P' + Omega, Q - P*pi).

    confidence = 0  -> posterior = prior (exact branch).
    confidence = 1  -> posterior = views Q (exact branch).
    """
    order = list(prior_excess.index)
    pi = prior_excess.to_numpy(float)
    C = covariance.loc[order, order].to_numpy(float)
    Qv = np.asarray(Q, dtype=float)
    if confidence is not None:
        if float(confidence) <= 0.0:
            return pd.Series(pi.copy(), index=order)
        if float(confidence) >= 1.0 - 1e-12:
            # Full trust in absolute views (P = identity): posterior = Q.
            return pd.Series(Qv.copy(), index=order)
    tauC = float(tau) * C
    middle = P @ tauC @ P.T + np.asarray(omega, dtype=float)
    rhs = Qv - P @ pi
    try:
        sol = np.linalg.solve(middle, rhs)
    except np.linalg.LinAlgError as exc:
        raise RuntimeError(f"BL posterior solve failed: {exc}") from exc
    post = pi + tauC @ P.T @ sol
    out = pd.Series(np.asarray(post, float), index=order)
    if not np.isfinite(out.to_numpy()).all():
        raise RuntimeError("BL posterior contains NaN/Inf")
    return out


def bl_full_pass(covariance: pd.DataFrame, risky_order, w_risky: pd.Series,
                 strategic_er: pd.Series, risk_free_rate: float,
                 neutral_expected_return: float, neutral_volatility: float,
                 tau: float, confidence: float) -> dict:
    """One full BL pass returning every intermediate for audit."""
    delta = compute_delta(neutral_expected_return, neutral_volatility, risk_free_rate)
    pi = implied_equilibrium_returns(covariance.loc[risky_order, risky_order],
                                     w_risky.loc[risky_order], delta)
    P, Q = build_cma_views(strategic_er, risk_free_rate, risky_order)
    omega = build_view_uncertainty(covariance.loc[risky_order, risky_order], P, tau, confidence)
    post_excess = black_litterman_posterior(pi, covariance.loc[risky_order, risky_order],
                                            P, Q, omega, tau, confidence)
    post_abs = post_excess + float(risk_free_rate)
    prior_abs = pi + float(risk_free_rate)
    return {"delta": delta, "prior_excess": pi, "prior_abs": prior_abs,
            "P": P, "Q": Q, "omega": omega, "posterior_excess": post_excess,
            "posterior_abs": post_abs}
