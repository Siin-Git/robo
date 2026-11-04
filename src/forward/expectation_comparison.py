"""Subtract only prospectively recorded estimates with matching measurement contracts.

No forecasts are reconstructed and no short-period return is annualized.
The caller supplies actuals calculated by the existing ledger engine.
"""
import math

AXES = ("start", "end", "currency", "cost_basis", "dividend_basis",
        "return_definition", "sampling", "portfolio_reference", "benchmark_reference")


def compare_metric(name, expected, actual):
    reasons = []
    ev, av = expected.get("value"), actual.get("value")
    if ev is None:
        reasons.append("ORIGINAL_METRIC_UNAVAILABLE")
    elif not isinstance(ev, (int, float)) or not math.isfinite(ev):
        reasons.append("ORIGINAL_METRIC_INVALID")
    if av is None:
        reasons.append("INSUFFICIENT_ACTUAL_HISTORY")
    elif not isinstance(av, (int, float)) or not math.isfinite(av):
        reasons.append("ACTUAL_METRIC_INVALID")
    definition = expected.get("definition")
    actual_definition = actual.get("definition", {})
    alignment = {}
    if not definition:
        reasons.append("ORIGINAL_COMPARISON_BASIS_NOT_RECORDED")
        definition = {}
    for axis in ("unit", *AXES):
        e = expected.get("unit") if axis == "unit" else definition.get(axis)
        a = actual.get("unit") if axis == "unit" else actual_definition.get(axis)
        known = e is not None and a is not None and e != "UNKNOWN" and a != "UNKNOWN"
        match = known and e == a
        alignment[axis] = {"expected": e, "actual": a, "matches": match}
        if not known:
            reasons.append(axis.upper() + "_NOT_RECORDED")
        elif not match:
            reasons.append(axis.upper() + "_DIFFERS")
    if actual.get("quality_reason"):
        reasons.append(actual["quality_reason"])
    reasons = list(dict.fromkeys(reasons))
    return {"metric": name, "expected": expected, "actual": actual, "alignment": alignment,
            "difference": av - ev if not reasons else None,
            "difference_unit": expected.get("unit"), "difference_direction": "ACTUAL_MINUS_EXPECTED",
            "status": "COMPARABLE" if not reasons else "NOT_COMPARABLE",
            "reason": reasons[0] if reasons else None, "reasons": reasons}


def ledger_comparisons(expectations, report, decision_id, core_version):
    result = []
    quality = report["quality"]
    for name, expected in expectations.items():
        metric = "cumulative_return" if name == "expected_return" else name
        risk = name in ("volatility", "tracking_error")
        actual = {"value": report["metrics"].get(metric),
            "unit": "fraction_per_year" if risk else "fraction",
            "start": report["start"], "end": report["end"], "basis": "RECORDED_NAV",
            "definition": {"start": report["start"], "end": report["end"], "currency": "KRW",
                "cost_basis": "TRANSACTION_COSTS_INCLUDED", "dividend_basis": "PROVIDER_ADJUSTED_OR_CLOSE",
                "return_definition": "STD_SAMPLE_ACTIVE_RETURNS" if name == "tracking_error" else
                                     "STD_SAMPLE_RETURNS" if risk else "NAV_CHANGE_NO_EXTERNAL_FLOWS",
                "sampling": "D_252" if risk else "OBSERVED_ENDPOINTS",
                "portfolio_reference": decision_id,
                "benchmark_reference": core_version if name == "tracking_error" else "NONE"},
            "quality_reason": ("ACTUAL_RISK_OBSERVATION_GAPS" if risk and
                (quality["missing_nav_dates"] or quality["stale_observations"]) else None)}
        result.append(compare_metric(name, expected, actual))
    return result
