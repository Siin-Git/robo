"""Explicit reviewed benchmarks, separate from trading prices and CORE accounts."""
import csv
import math
import pandas as pd
import yaml
from ...forward.reference_portfolio import evaluate_levels
from . import _common as C


def definitions():
    return yaml.safe_load((C.ROOT / "config/performance_benchmarks.yaml").read_text(encoding="utf-8"))


def reference(key, label, report, config=None):
    cfg = config if config is not None else definitions()
    definition = cfg["definitions"].get(key)
    start, end = report["start"], report["end"]
    row = {"key": key, "label": label, "start": start, "end": end, "status": "UNAVAILABLE",
           "return": None, "difference": None, "reason": "BENCHMARK_DEFINITION_NOT_CONFIGURED",
           "candidates": cfg["candidates"].get(key, []), "definition_version": cfg["version"]}
    if not definition:
        return row
    required = ("id", "label", "currency", "dividends", "costs", "method", "approved_by", "approved_at", "version")
    if any(not definition.get(field) for field in required) or definition.get("approved") is not True:
        row["reason"] = "BENCHMARK_DEFINITION_NOT_APPROVED"
        return row
    row.update(label=definition["label"], definition=definition, source="REVIEWED_REFERENCE_LEVELS",
               actual_account_history=False, definition_version=definition["version"])
    if definition["currency"] != "KRW":
        row["reason"] = "BENCHMARK_CURRENCY_DIFFERS"
        return row
    if not start or not end or start >= end or report["metrics"]["cumulative_return"] is None:
        row["reason"] = "INSUFFICIENT_ACTUAL_HISTORY"
        return row
    try:
        if definition["method"] == "KRW_CASH_ZERO":
            levels = pd.DataFrame({"reference": [1., 1.]}, index=pd.to_datetime([start, end]))
        elif definition["method"] == "SUPPLIED_LEVELS":
            path = (C.ROOT / definition["data_file"]).resolve()
            allowed = (C.ROOT / "data/reference_benchmarks").resolve()
            if allowed not in path.parents:
                raise ValueError("BENCHMARK_DATA_PATH_INVALID")
            with path.open(encoding="utf-8") as file:
                points = list(csv.DictReader(file))
            dates = [p["date"] for p in points]
            if dates != sorted(set(dates)):
                raise ValueError("BENCHMARK_DATES_NOT_UNIQUE_AND_ORDERED")
            levels = pd.DataFrame({"reference": [float(p["level"]) for p in points]}, index=pd.to_datetime(dates))
            if not all(math.isfinite(v) and v > 0 for v in levels.reference):
                raise ValueError("BENCHMARK_LEVELS_INVALID")
        else:
            raise ValueError("BENCHMARK_METHOD_UNSUPPORTED")
        nav = evaluate_levels({"reference": 1.}, levels, start, end)
        row.update(status="AVAILABLE", reason=None, **{"return": float(nav.nav.iloc[-1] / nav.nav.iloc[0] - 1)})
        # A gross reference and a net account can be shown together, but that
        # does not create a matched financial-definition subtraction.
        row["difference_reason"] = "REFERENCE_COST_OR_DIVIDEND_BASIS_DIFFERS"
        if definition["costs"] == "TRANSACTION_COSTS_INCLUDED" and definition["dividends"] == "PROVIDER_ADJUSTED_OR_CLOSE":
            row["difference"] = report["metrics"]["cumulative_return"] - row["return"]
            row["difference_reason"] = None
    except (OSError, ValueError, KeyError) as exc:
        row["reason"] = str(exc) if isinstance(exc, ValueError) else "BENCHMARK_DATA_UNAVAILABLE"
    return row
