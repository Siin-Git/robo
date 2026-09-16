"""Covariance: shape, symmetry, PSD."""
import numpy as np
import pandas as pd

from src.risk.covariance import (
    annualize_covariance,
    corr_from_cov,
    ledoit_wolf_covariance,
    vols_from_cov,
)


def _sample_returns(n=200, k=9, seed=1):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0.001, 0.02, size=(n, k)),
                        columns=[f"a{i}" for i in range(k)])


def test_cov_shape_and_symmetry():
    r = _sample_returns()
    cov = ledoit_wolf_covariance(r)
    assert cov.shape == (9, 9)
    np.testing.assert_allclose(cov.to_numpy(), cov.to_numpy().T, atol=1e-10)
    assert cov.notna().all().all()
    assert np.isfinite(cov.to_numpy()).all()


def test_cov_psd():
    r = _sample_returns()
    cov = ledoit_wolf_covariance(r)
    vals = np.linalg.eigvalsh(cov.to_numpy())
    assert vals.min() > -1e-8


def test_annualize_vols_corr():
    r = _sample_returns()
    cov3 = annualize_covariance(ledoit_wolf_covariance(r), 52)
    vols = vols_from_cov(cov3)
    assert (vols > 0).all()
    corr = corr_from_cov(cov3)
    np.testing.assert_allclose(np.diag(corr.to_numpy()), np.ones(9), atol=1e-8)
    assert ((corr.to_numpy() >= -1.0) & (corr.to_numpy() <= 1.0)).all()
