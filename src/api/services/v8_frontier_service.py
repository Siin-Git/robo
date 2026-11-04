"""Read-only V8 backtest comparison; excluded from portfolio optimization."""
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import math

import numpy as np
import pandas as pd

from src.portfolio.optimizer import portfolio_stats
from src.risk.covariance import annualize_covariance, ledoit_wolf_covariance
from . import _common as C
from .strategy_frontier_service import comparison as composition_comparison

ARTIFACT = "data/strategy_research/v8_ma_mdd_us_curve.csv"


def calculate(raw: bytes, period: dict) -> dict:
    frame = pd.read_csv(BytesIO(raw))
    if list(frame.columns) != ["date", "portfolio_value_usd"] or frame.empty:
        raise ValueError("V8_CURVE_COLUMNS_INVALID")
    dates = pd.DatetimeIndex(pd.to_datetime(frame["date"], format="%Y-%m-%d"))
    levels = pd.Series(frame["portfolio_value_usd"].to_numpy(dtype=float), index=dates)
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing or not np.isfinite(levels).all() or (levels <= 0).any():
        raise ValueError("V8_CURVE_INVALID")
    # Same W-FRI convention as the existing composition estimates. Retain the
    # preceding week's level, reject missing weeks, and exclude the later partial week.
    weekly = levels.resample("W-FRI").last().pct_change(fill_method=None)
    returns = weekly.loc[period["start"]:period["end"]].to_frame("v8")
    if len(returns) < 52 or len(returns) != period["observations"] or not np.isfinite(returns.to_numpy()).all():
        raise ValueError("V8_COMMON_HISTORY_INSUFFICIENT")
    cov = annualize_covariance(ledoit_wolf_covariance(returns), 52)
    ret, vol, sharpe = portfolio_stats(np.array([1.0]), (returns.mean() * 52).to_numpy(), cov.to_numpy(), .03)
    if not all(math.isfinite(v) for v in (ret, vol, sharpe)):
        raise ValueError("V8_ESTIMATE_INVALID")
    return {
        "id": "v8_surge", "label": "V8 급등주 전략",
        "expected_return": ret, "volatility": vol, "sharpe": sharpe,
        "risk_free_rate": .03, "currency": "USD", "validation_status": "PROVISIONAL",
        "data_kind": "BACKTEST_EQUITY_CURVE", "actual_account_history": False,
        "confirmation_eligible": False, "optimization_eligible": False,
        "return_basis": "WEEKLY_ARITHMETIC_MEAN_ANNUALIZED_52",
        "risk_basis": "SINGLE_SERIES_WEEKLY_LEDOIT_WOLF_ANNUALIZED_52",
        "period": dict(period), "snapshot_date": str(dates[-1].date()), "weights": [],
        "source_file": "v8_ma_mdd_us_curve.csv", "artifact_sha256": sha256(raw).hexdigest(),
        "source_period": {"start": str(dates[0].date()), "end": str(dates[-1].date()), "observations": len(levels)},
        "note": "USD 기준 검증 전 백테스트(PROVISIONAL)입니다. 기존 두 전략과 같은 기간의 주간 평균 수익률·변동성으로 재계산했으며 CAGR이 아닙니다. 입출금과 비용 반영 여부는 원본 백테스트 검증이 필요합니다. 기본 Frontier와 통화·예측 기준이 다릅니다.",
    }


@lru_cache(maxsize=1)
def comparison() -> dict:
    return calculate((C.ROOT / ARTIFACT).read_bytes(), composition_comparison()["period"])
