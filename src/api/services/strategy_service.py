"""Authenticated research reads; supplied model levels never enter PriceDaily."""
from copy import deepcopy
import json
import yaml
from ...forward.performance_report import calculate_report
from ..errors import ApiError, not_found
from . import _common as C

RESEARCH_THEME_IDS = frozenset({"leader_stock", "export_stock"})


def require_executable(theme_ids):
    if RESEARCH_THEME_IDS.intersection(theme_ids):
        raise ApiError("STRATEGY_RESEARCH_ONLY", "모델 정의·갱신 입력·집행 경로 검증 전에는 자료 조회만 가능합니다.", 422)


def bundle():
    cfg = yaml.safe_load((C.ROOT / "config/strategy_research.yaml").read_text(encoding="utf-8"))
    data = json.loads((C.ROOT / cfg["artifact"]).read_text(encoding="utf-8"))
    if cfg["version"] != data["version"] or data["data_kind"] != "HISTORICAL_MODEL_BACKTEST":
        raise ApiError("STRATEGY_SOURCE_INVALID", "전략 자료 버전이 일치하지 않습니다.", 503)
    return cfg, data


def catalog():
    cfg, data = bundle()
    return {"version": cfg["version"], "items": [dict(id=key, **deepcopy(value),
        status="RESEARCH_ONLY", operational=False, frontier_eligible=False,
        confirmation_eligible=False, price_store_eligible=False)
        for key, value in cfg["strategies"].items()], "sources": data["sources"]}


def detail(strategy_id, variant_id=None):
    cfg, data = bundle()
    strategy = cfg["strategies"].get(strategy_id)
    if not strategy:
        raise not_found("STRATEGY_NOT_FOUND", "전략 자료를 찾을 수 없습니다.")
    # No default variant: callers must explicitly select one for numeric history.
    result = dict(id=strategy_id, **deepcopy(strategy), status="RESEARCH_ONLY", operational=False,
                  version=cfg["version"], sources=data["sources"], report=None)
    snapshot = deepcopy(data["snapshots"][strategy["snapshot"]])
    if "items" in snapshot:
        result["snapshot_count"] = len(snapshot["items"])
        result["snapshot"] = snapshot["items"][-1]
        result["snapshot_quality"] = {"max_weight_reconciliation_error": snapshot["max_weight_reconciliation_error"]}
    else:
        result["snapshot"] = snapshot
    if variant_id is None:
        return result
    variant = next((v for v in strategy["variants"] if v["id"] == variant_id), None)
    if not variant:
        raise not_found("STRATEGY_VARIANT_NOT_FOUND", "전략 변형을 선택해 주세요.")
    series = data["series"][variant_id]
    # Reuse the existing endpoint-return/MDD calculator, without account writes.
    report = calculate_report([{"date": p["date"], "nav": p["level"], "cash": 0}
                               for p in series["points"]], [], [], [])
    report["data_kind"] = "HISTORICAL_MODEL_BACKTEST"
    report["quality"] = deepcopy(series["quality"])
    report["metrics"] = {key: report["metrics"][key] for key in ("cumulative_return", "mdd")}
    report.pop("assets")
    report.pop("attribution")
    # These are dimensionless model levels. Never expose them as KRW account NAV.
    report.pop("valuation")
    report.pop("anchor")
    report.update(frequency=variant["frequency"], units={"level": "model_index", "returns": "fraction"},
                  mdd_basis="OBSERVED_SOURCE_LEVELS", actual_account_history=False)
    if variant["frequency"] == "MONTHLY":
        report.update(date_semantics="MONTH_END_LABEL_NOT_EXECUTION_DATE",
            source_period={"start": "2012-01-30", "end": "2026-09-29"},
            warning="월말 라벨(마지막 9/30)은 실제 평가일이 아닙니다. 자료의 백테스트 종료일은 9/29이며 일별 경로는 없습니다.")
    result.update(variant=variant, report=report, source_summary=data["source_summary"][variant_id],
        source_summary_basis="SUPPLIED_FULL_PERIOD_STATISTICS_NOT_FORECAST", snapshot_applies_to_variant=False)
    return result
