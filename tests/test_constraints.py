"""Constraint validation tests."""
import numpy as np
import yaml
from pathlib import Path

from src.portfolio.constraints import ASSET_ORDER, project_box_simplex, validate_weights, get_bounds

ROOT = Path(__file__).resolve().parents[1]
BOUNDS = yaml.safe_load(open(ROOT / "config" / "optimizer_v0.yaml"))["weight_bounds"]
GROUPS = yaml.safe_load(open(ROOT / "config" / "optimizer_v0.yaml"))["group_constraints"]


def test_equal_weight_violations_are_detected():
    # 1/9 ~= 11.1% mechanically exceeds the 10% global_reit cap and the
    # 20% gold+REIT group cap; validation must flag this transparently.
    w = np.full(9, 1 / 9)
    issues = validate_weights(w, ASSET_ORDER, BOUNDS, GROUPS)
    assert any("global_reit" in i and "above max" in i for i in issues)
    assert any("group" in i for i in issues)


def test_upper_bound_violation_detected():
    w = np.full(9, 1 / 9)
    w[0] = 0.90
    w[1:] = 0.10 / 8
    issues = validate_weights(w, ASSET_ORDER, BOUNDS, GROUPS)
    assert any("above max" in i for i in issues)


def test_group_violation_detected():
    w = np.zeros(9)
    w[0] = 0.35
    w[1] = 0.25
    w[2] = 0.10  # equity = 0.70 ok
    w[7] = 0.15
    w[8] = 0.10  # real = 0.25 > 0.20 violates
    w[4] = 0.05
    assert abs(w.sum() - 1.0) < 1e-12
    issues = validate_weights(w, ASSET_ORDER, BOUNDS, GROUPS)
    assert any("group" in i for i in issues)


def test_projection_respects_box_simplex():
    rng = np.random.default_rng(0)
    lb, ub = get_bounds(ASSET_ORDER, BOUNDS)
    for _ in range(20):
        v = rng.normal(0, 1, size=9)
        w = project_box_simplex(v, lb, ub)
        assert abs(w.sum() - 1.0) < 1e-9
        assert (w >= lb - 1e-9).all() and (w <= ub + 1e-9).all()
