"""Ledoit-Wolf shrinkage covariance (sklearn when available, else pure-numpy).

Manual implementation follows Ledoit & Wolf (2004).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ledoit_wolf_manual(X: np.ndarray) -> np.ndarray:
    """X: (T, N) returns. Returns shrunk covariance (N, N)."""
    T, N = X.shape
    if T < 3 or N < 1:
        raise ValueError("Not enough observations for covariance")
    mean = X.mean(axis=0)
    Xc = X - mean
    S = (Xc.T @ Xc) / T
    mu = float(np.trace(S) / N)
    F = mu * np.eye(N)
    pi_hat = 0.0
    rho_num = 0.0
    for i in range(N):
        for j in range(N):
            y = Xc[:, i] * Xc[:, j]
            s_ij = float(S[i, j])
            pi_hat += float(((y - s_ij) ** 2).mean())
            f_ij = mu if i == j else 0.0
            rho_num += float(((y - s_ij) * (f_ij - s_ij)).mean())
    gamma = float(((S - F) ** 2).sum())
    if gamma == 0.0:
        return S.copy()
    kappa = (pi_hat - rho_num) / gamma
    delta = max(0.0, min(1.0, kappa / T))
    return delta * F + (1.0 - delta) * S


def ledoit_wolf_covariance(weekly_returns: pd.DataFrame) -> pd.DataFrame:
    """Shrunk weekly covariance as DataFrame. Prefers sklearn if installed."""
    X = weekly_returns.to_numpy(dtype=float)
    X = X[np.isfinite(X).all(axis=1)]
    if len(X) < 10:
        raise ValueError("Not enough finite observations for covariance")
    try:
        from sklearn.covariance import LedoitWolf  # type: ignore

        lw = LedoitWolf().fit(X)
        cov = np.asarray(lw.covariance_, dtype=float)
        method = "sklearn"
    except Exception:
        cov = _ledoit_wolf_manual(X)
        method = "manual"
    cov = 0.5 * (cov + cov.T)
    vals, vecs = np.linalg.eigh(cov)
    if float(vals.min()) < 0:
        vals = np.clip(vals, 1e-12, None)
        cov = (vecs * vals) @ vecs.T
        cov = 0.5 * (cov + cov.T)
    out = pd.DataFrame(cov, index=weekly_returns.columns, columns=weekly_returns.columns)
    out.attrs["method"] = method
    return out


def annualize_covariance(weekly_cov: pd.DataFrame, factor: int = 52) -> pd.DataFrame:
    return weekly_cov * float(factor)


def vols_from_cov(annual_cov: pd.DataFrame) -> pd.Series:
    return pd.Series(
        {c: float(np.sqrt(max(annual_cov.loc[c, c], 0.0))) for c in annual_cov.columns}
    )


def corr_from_cov(cov: pd.DataFrame) -> pd.DataFrame:
    v = np.sqrt(np.clip(np.diag(cov.to_numpy(float)), 1e-18, None))
    c = cov.to_numpy(float) / np.outer(v, v)
    c = np.clip(c, -1.0, 1.0)
    return pd.DataFrame(c, index=cov.index, columns=cov.columns)
