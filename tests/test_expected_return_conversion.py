"""Expected return conversion tests."""
from src.expected_return.conversions import geometric_to_arithmetic


def test_geo_to_arith_basic():
    assert abs(geometric_to_arithmetic(0.06, 0.10) - (0.06 + 0.5 * 0.01)) < 1e-12


def test_geo_to_arith_zero_vol():
    assert abs(geometric_to_arithmetic(0.05, 0.0) - 0.05) < 1e-12


def test_geo_to_arith_monotone_in_vol():
    a = geometric_to_arithmetic(0.05, 0.10)
    b = geometric_to_arithmetic(0.05, 0.20)
    assert b > a
