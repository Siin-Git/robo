"""Retrospective current-weight comparison. Never writes account NAV or trades."""
from functools import lru_cache
from pathlib import Path
from datetime import timedelta
import hashlib
import json
import os

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ...forward.metrics import perf_metrics, tracking_ir
from ...local.capstone import enabled as capstone_enabled
from ...db.models.account import Account
from ...db.models.portfolio import PortfolioTarget
from ...db.models.base_selection import BasePortfolioSelection
from ...db.models.onboarding import OnboardingDraft
from ...db.models.user import User
from . import _common as C
from ..errors import ApiError


def enabled():
    return capstone_enabled() and os.environ.get("CAPSTONE_MARKET_COMPARISON") == "1"


@lru_cache(maxsize=1)
def bundle():
    root = C.ROOT / "data/market"
    meta = json.loads((root / "manifest.json").read_text())
    path = root / "prices_20260911.csv.gz"
    if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
        raise ApiError("MARKET_DATA_INVALID", "가격 데이터 검증에 실패했습니다.", 503)
    prices = pd.read_csv(path, index_col="date", parse_dates=True)
    if prices.index.has_duplicates or not prices.index.is_monotonic_increasing or not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ApiError("MARKET_DATA_INVALID", "가격 데이터가 올바르지 않습니다.", 503)
    return prices, meta


def price_date():
    return bundle()[0].index[-1].date()


def risk_cov(asset_ids, asof, weeks=260):
    return _risk_cov(tuple(sorted(set(asset_ids))), str(asof), weeks).copy()


@lru_cache(maxsize=256)
def _risk_cov(asset_ids, asof, weeks):
    levels, _ = bundle()
    if any(a not in levels.columns for a in asset_ids):
        raise ApiError("MARKET_DATA_MISSING", "선택 자산의 가격 데이터가 없습니다.", 422)
    from ...risk.covariance import annualize_covariance, ledoit_wolf_covariance
    weekly = levels.loc[:asof, list(asset_ids)].resample("W-FRI").last().pct_change(fill_method=None).dropna()
    if len(weekly) < weeks:
        raise ApiError("MARKET_DATA_INSUFFICIENT", "위험 계산에 필요한 가격 기간이 부족합니다.", 422)
    return annualize_covariance(ledoit_wolf_covariance(weekly.iloc[-weeks:]), 52)


def design_configuration(session, user):
    """Read only a completed design, not an autosaved draft or foreign identity."""
    # 설계 DB 는 읽기만 한다. SQLite 는 URI 로 읽기 전용을 걸 수 있고,
    # PostgreSQL 은 그런 수단이 없어 평범하게 연다(이 함수가 쓰기를 하지 않는다).
    #
    # 설계 DB 는 **인증 DB 를 따라간다**. 환경변수를 먼저 보면, 개발자의
    # .env.local 에 운영 URL 이 있을 때 임시 DB 로 도는 테스트가 운영 DB 를
    # 열게 된다(design_workspace.design_database_url 과 같은 규칙).
    import os
    auth_url = session.get_bind().url
    if auth_url.drivername.split("+", 1)[0] != "sqlite":
        from ...db.config import normalize_pg_url
        explicit = os.environ.get("CAPSTONE_DESIGN_DATABASE_URL", "").strip()
        if not explicit:
            return None
        engine = create_engine(normalize_pg_url(explicit))
    else:
        source = auth_url.database
        if not source or source == ":memory:":
            return None
        path = Path(source).resolve().with_name("portfolio_design.db")
        if not path.is_file():
            return None
        engine = create_engine(f"sqlite:///file:{path}?mode=ro&uri=true")
    from .enrollment_service import latest_reset
    reset = latest_reset(session, user.participant_id)
    try:
        with Session(engine) as db:
            selection = db.scalar(select(BasePortfolioSelection).where(BasePortfolioSelection.user_id == user.user_id,
                BasePortfolioSelection.participant_id == user.participant_id, BasePortfolioSelection.status == "active"))
            identity = db.get(User, user.user_id)
            if not selection or not identity or identity.email_normalized != user.email_normalized:
                return None
            account = db.scalar(select(Account).where(Account.participant_id == user.participant_id, Account.account_type == "personal"))
            target = db.scalar(select(PortfolioTarget).where(PortfolioTarget.account_id == account.account_id)
                .order_by(PortfolioTarget.created_at.desc(), PortfolioTarget.target_id.desc())) if account else None
            if not target:
                return None
            if reset and target.created_at.replace(tzinfo=None) <= reset.timestamp.replace(tzinfo=None):
                return None
            # The reason belongs to this saved target, never a newer unfinished draft.
            from ...db.models.event import Event
            event = db.scalar(select(Event).where(Event.participant_id == user.participant_id,
                Event.event_type == "ONBOARDING_COMPLETED").order_by(Event.timestamp.desc(), Event.event_id.desc()))
            draft = db.get(OnboardingDraft, user.user_id)
            reason = (event.payload_json or {}).get("reason") if event else None
            if reason is None and draft and draft.completed_at:
                reason = draft.reason
            return {"weights": dict(target.weights_json), "reason": reason or "",
                "frontier_id": selection.frontier_id, "confirmed_at": target.created_at.isoformat()}
    finally:
        engine.dispose()


def configuration(session, user, slot=None):
    if slot and not slot.confirmed_at:
        raise ApiError("SETUP_REQUIRED", "포트폴리오 선택을 먼저 완료해 주세요.", 409)
    selected = design_configuration(session, user)
    if selected:
        return selected
    if slot:
        if not slot.confirmed_at:
            raise ApiError("SETUP_REQUIRED", "포트폴리오 선택을 먼저 완료해 주세요.", 409)
        cfg = slot.configuration_json
        return {"weights": {(('theme:' + w['asset_id']) if w['asset_type'] == 'theme' else w['asset_id']): w['weight'] for w in cfg['allocation']},
                "reason": cfg.get("reason", ""), "frontier_id": cfg.get("frontier_id") or cfg.get("core_id"), "confirmed_at": slot.confirmed_at.isoformat()}
    account = session.scalar(select(Account).where(Account.participant_id == user.participant_id, Account.account_type == "personal"))
    target = session.scalar(select(PortfolioTarget).where(PortfolioTarget.account_id == account.account_id)
        .order_by(PortfolioTarget.created_at.desc(), PortfolioTarget.target_id.desc())) if account else None
    if not target:
        raise ApiError("PORTFOLIO_NOT_READY", "저장된 포트폴리오가 없습니다.", 409)
    return {"weights": dict(target.weights_json), "reason": "기존 참가자의 저장된 구성", "frontier_id": "CORE_V0.3", "confirmed_at": target.created_at.isoformat()}


def evaluate(weights):
    """Buy-and-hold from the common start, using current weights (gross of costs)."""
    prices, meta = bundle()
    if not weights or any(not np.isfinite(w) or w < 0 for w in weights.values()) or abs(sum(weights.values()) - 1) > 1e-6:
        raise ApiError("INVALID_WEIGHTS", "포트폴리오 비중을 확인해 주세요.", 422)
    active = {k: float(v) for k, v in weights.items() if v > 0 and k != "cash"}
    missing = set(active) - set(prices.columns)
    if missing:
        raise ApiError("MARKET_DATA_MISSING", "선택 자산의 가격 데이터가 없습니다.", 422)
    levels = prices.loc[meta["comparison_start"]:meta["comparison_end"], list(active)]
    if len(levels) < 31 or str(levels.index[0].date()) != meta["comparison_start"] or str(levels.index[-1].date()) != meta["comparison_end"]:
        raise ApiError("MARKET_DATA_INSUFFICIENT", "공통 비교 기간의 가격 데이터가 부족합니다.", 422)
    nav = ((levels / levels.iloc[0]).mul(pd.Series(active)).sum(axis=1) + weights.get("cash", 0)) * 100
    return pd.DataFrame({"nav": nav, "daily_return": nav.pct_change(fill_method=None).fillna(0)})


def report(session, user, slot=None):
    from .portfolio_service import _legs, _tickers
    cfg = configuration(session, user, slot)
    core, _ = C.frozen_bundle()
    p, c = evaluate(cfg["weights"]), evaluate(core)
    pm, cm, relative = perf_metrics(p), perf_metrics(c), tracking_ir(p, c)
    monday = p.index[-1].date() - timedelta(days=p.index[-1].weekday())
    baseline = p.index[p.index.date < monday][-1]
    pr = float(p.nav.iloc[-1] / p.loc[baseline, "nav"] - 1)
    cr = float(c.nav.iloc[-1] / c.loc[baseline, "nav"] - 1)
    tickers = _tickers(session)
    return {"participant_id": user.participant_id, "display_name": user.participant.display_name,
        "themes": [a[6:] for a in cfg["weights"] if a.startswith("theme:") and cfg["weights"][a] > 0],
        "reason": cfg["reason"], "frontier_id": cfg["frontier_id"], "benchmark": "CORE_V0.3",
        "data_source": "MARKET_PRICE_REPLAY", "risk_free_rate": 0, "status": "ready",
        "start": str(p.index[0].date()), "end": str(p.index[-1].date()), "observations": len(p),
        "confirmed_at": cfg["confirmed_at"], "forward_started_at": None,
        "metrics": {"nav": float(p.nav.iloc[-1]), "cumulative_return": pm["cumulative_return"],
            "core_return": cm["cumulative_return"], "excess_return": pm["cumulative_return"]-cm["cumulative_return"],
            "mdd": pm["mdd"], "volatility": pm["annualized_volatility"], "sharpe": pm["sharpe"],
            "tracking_error": relative["tracking_error"], "information_ratio": relative["information_ratio"], "sortino": None},
        "core_metrics": {"cumulative_return": cm["cumulative_return"], "mdd": cm["mdd"],
            "volatility": cm["annualized_volatility"], "sharpe": cm["sharpe"]},
        "weekly": {"week_start": monday.isoformat(), "start": str(baseline.date()), "end": str(p.index[-1].date()),
            "portfolio_return": pr, "core_return": cr, "excess_return": pr-cr},
        "series": [{"date": str(d.date()), "personalized_nav": float(p.loc[d, "nav"]), "core_nav": float(c.loc[d, "nav"])} for d in p.index],
        "allocation": _legs(cfg["weights"], tickers), "core_allocation": _legs(core, tickers),
        "evaluation": {"method": "current-weight buy-and-hold", "costs_included": False,
            "market_data_version": bundle()[1]["version"], "actual_account_history": False}}
