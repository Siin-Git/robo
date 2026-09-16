"""Geometric -> arithmetic conversion for MVO."""
from __future__ import annotations


def geometric_to_arithmetic(mu_geo: float, annual_vol: float) -> float:
    """mu_arith ~= mu_geo + 0.5 * sigma^2."""
    if annual_vol < 0:
        raise ValueError("annual_vol must be non-negative")
    return float(mu_geo) + 0.5 * float(annual_vol) ** 2
