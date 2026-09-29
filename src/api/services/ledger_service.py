"""운용 기록 상태와 사용자 알림.

새 테이블을 만들지 않는다. 상태는 ``nav_daily``·``prices_daily`` 에서,
알림은 append-only 인 ``events`` 에서 읽어 사용자용으로 번역한다.
리밸런싱 판정은 기존 주문 엔진의 band 정책을 재사용한다.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from ...db.models.account import Account as _A
from ...db.models.event import Event as _E
from ...db.models.nav import NavDaily as _N
from ...db.models.price import PriceDaily as _Px
from ...db.models.holding import Holding
from ...db.models.order import Order
from ...db.models.portfolio import PortfolioTarget
from ...forward.execution import within_band
from ...forward.rebalance_schedule import next_rebalance_effective
from ..errors import not_found
from . import _common as C

# events.event_type -> 사용자 알림 정의.
# 여기에 없는 이벤트(로그인, 세션 등)는 알림으로 내보내지 않는다.
ALERT_RULES: dict[str, tuple[str, str, str]] = {
    # event_type: (알림 type, severity, 제목)
    "INITIAL_BENCHMARK_ORDER_CREATED": ("INITIAL_ORDER", "info", "최초 포트폴리오 주문이 생성되었습니다"),
    "ORDER_CREATED": ("ORDER_CREATED", "info", "주문이 생성되었습니다"),
    "TRADE_EXECUTED": ("TRADE_EXECUTED", "info", "주문이 체결되었습니다"),
    "ACTIVE_REBALANCE": ("REBALANCE_EXECUTED", "info", "리밸런싱이 실행되었습니다"),
    "CASH_SCALED": ("CASH_SCALED", "warning", "현금이 부족해 매수 수량이 축소되었습니다"),
    "RISK_MODEL_REFRESHED": ("RISK_REFRESHED", "info", "위험 모형이 갱신되었습니다"),
    "BASE_PORTFOLIO_SELECTED": ("BASE_SELECTED", "info", "기본 포트폴리오를 선택했습니다"),
    "ONBOARDING_COMPLETED": ("ONBOARDING_COMPLETED", "info", "포트폴리오 설정을 완료했습니다"),
    "VIEW_SUBMITTED": ("VIEW_SUBMITTED", "info", "주간 투자 의견을 제출했습니다"),
    "VIEW_REJECTED": ("VIEW_REJECTED", "warning", "투자 의견이 반려되었습니다"),
    "FORWARD_TEST_LAUNCHED": ("FORWARD_LAUNCHED", "info", "모의운용이 시작되었습니다"),
    "PRICE_REFRESH_FAILED": ("PRICE_REFRESH_FAILED", "warning", "가격 수집에 실패했습니다"),
}

# 특정 사용자가 아니라 운용 전체에 해당하는 이벤트. participant_id·account_id 가
# 비어 있으므로 사용자 범위 필터와 별도로 포함한다.
SYSTEM_ALERT_TYPES = ("PRICE_REFRESH_FAILED",)

# PRICE_REFRESH 는 매일 남지만 알림이 아니다. 조회 구간에 거래일이 없으면
# (휴장·마감 전) 매번 예외가 나므로 그것까지 알리면 거짓 경보가 된다.
# 사용자에게 의미 있는 것은 가격이 실제로 밀린 경우이고, 그것은 status() 의
# data_freshness 와 PRICE_STALE 알림이 이미 담당한다.

STALE_DAYS_DEFAULT = 14


def _accounts(session, participant_id: str):
    rows = list(session.scalars(select(_A).where(_A.participant_id == participant_id)))
    if not rows:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")
    personal = next((a for a in rows if a.account_type == "personal"), None)
    core = next((a for a in rows if a.account_type == "core"), None)
    return personal, core


def _stale_days() -> int:
    try:
        return int(C.load_forward_cfg()["forward_test"].get("stale_price_days",
                                                            STALE_DAYS_DEFAULT))
    except Exception:
        return STALE_DAYS_DEFAULT


def _next_rebalance(last: date | None) -> str | None:
    """엔진과 같은 월간/분기 효력일 규칙. 휴일 체결은 실제 종가에 따른다."""
    if last is None:
        return None
    try:
        freq = C.load_forward_cfg()["forward_test"]["core_rebalance"]["frequency"]
        upcoming = next_rebalance_effective(max(last, date.today()), freq)
    except (KeyError, ValueError):
        return None
    return upcoming.isoformat() if upcoming else None


def _rebalance_status(session, account_id: str, asof: date | None) -> dict:
    """평가일 현재 효력이 있는 목표와 같은 날의 실제 보유 내역을 비교한다.

    목표를 실제 보유량으로 대체하지 않는다. 누락/불완전한 평가에는 판정을
    내리지 않으며, pending 주문은 drift 판정과 별도로 그대로 노출한다.
    """
    band = C.load_forward_cfg()["forward_test"]["core_rebalance"].get("band")
    target = session.scalar(select(PortfolioTarget).where(
        PortfolioTarget.account_id == account_id,
        PortfolioTarget.effective_date <= (asof or date.today()),
    ).order_by(PortfolioTarget.effective_date.desc(), PortfolioTarget.created_at.desc(),
               PortfolioTarget.target_id.desc()).limit(1))
    nav = session.get(_N, (account_id, asof)) if asof else None
    holdings = list(session.scalars(select(Holding).where(
        Holding.account_id == account_id, Holding.date == asof))) if asof else []
    weights = {h.asset_id: float(h.weight) for h in holdings}
    targets = dict(target.weights_json) if target else {}
    orders = list(session.scalars(select(Order).where(
        Order.account_id == account_id, Order.status == "pending",
    ).order_by(Order.effective_at, Order.order_id)))
    # 평가가 전액 현금인 경우 보유 행이 없어도 위험자산 비중 0은 확정된다.
    has_holdings = bool(holdings) or bool(nav and nav.nav > 0 and nav.cash_balance == nav.nav)
    state = ("NO_VALUATION" if nav is None else
             "INCOMPLETE_VALUATION" if nav.nav_status != "OK" else
             "NO_HOLDINGS" if not has_holdings else
             "NO_TARGET" if target is None else "READY")
    rows = []
    for asset in sorted((set(targets) | set(weights) | {o.asset_id for o in orders}) - {"cash"}):
        tw = float(targets.get(asset, 0)) if target else None
        cw = weights.get(asset, 0.0) if has_holdings else None
        drift, action = "UNAVAILABLE", None
        if state == "READY":
            inside = abs(tw - cw) < 1e-9 or within_band(tw, cw, band)
            drift = "WITHIN_BAND" if inside else "OUTSIDE_BAND"
            action = "HOLD" if inside else "BUY" if tw > cw else "SELL"
        rows.append({
            "asset_id": asset, "target_weight": tw, "current_weight": cw,
            "drift_status": drift, "action": action,
            "pending_orders": [{"order_id": o.order_id, "side": o.side.upper(),
                                "effective_at": C.as_date(o.effective_at).isoformat()}
                               for o in orders if o.asset_id == asset],
        })
    return {"as_of": asof.isoformat() if asof else None, "status": state,
            "nav_status": nav.nav_status if nav else None,
            "target_effective_date": C.as_date(target.effective_date).isoformat() if target else None,
            "band": band, "assets": rows}


def status(session, participant_id: str) -> dict:
    """내 운용 기록의 존재 여부와 최신성."""
    personal, _core = _accounts(session, participant_id)
    if personal is None:
        return {"has_history": False, "first_valuation_date": None,
                "last_valuation_date": None, "observation_count": 0,
                "last_updated_at": None, "latest_price_date": None,
                "data_freshness": "NO_DATA", "next_rebalance_date": None,
                "stale_price_days": _stale_days(), "rebalance": None}

    row = session.execute(
        select(func.min(_N.date), func.max(_N.date), func.count())
        .where(_N.account_id == personal.account_id)).one()
    first_d, last_d, count = row[0], row[1], int(row[2] or 0)
    first_d = C.as_date(first_d) if first_d is not None else None
    last_d = C.as_date(last_d) if last_d is not None else None

    price_d = session.scalar(select(func.max(_Px.date)))
    price_d = C.as_date(price_d) if price_d is not None else None

    updated = session.scalar(
        select(func.max(_E.timestamp)).where(_E.account_id == personal.account_id))

    if count == 0 or price_d is None:
        freshness = "NO_DATA"
    else:
        gap = (date.today() - price_d).days
        freshness = "STALE" if gap > _stale_days() else "OK"

    return {
        "has_history": count > 0,
        "first_valuation_date": first_d.isoformat() if first_d else None,
        "last_valuation_date": last_d.isoformat() if last_d else None,
        "observation_count": count,
        "last_updated_at": updated.isoformat() if updated is not None else None,
        "latest_price_date": price_d.isoformat() if price_d else None,
        "data_freshness": freshness,
        "next_rebalance_date": _next_rebalance(last_d),
        "stale_price_days": _stale_days(),
        "rebalance": _rebalance_status(session, personal.account_id, last_d),
    }


def _alert_from_event(event) -> dict | None:
    rule = ALERT_RULES.get(event.event_type)
    if rule is None:
        return None
    alert_type, severity, title = rule
    payload = event.payload_json
    if isinstance(payload, str):          # SQLite 경로에서 문자열로 올 수 있다
        import json
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    ts = event.timestamp
    return {
        "alert_id": event.event_id,
        "type": alert_type,
        "date": ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10],
        "occurred_at": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
        "title": title,
        "detail": payload if isinstance(payload, dict) else {},
        "severity": severity,
    }


def alerts(session, participant_id: str, limit: int = 50, offset: int = 0) -> dict:
    """사용자용 알림 목록. 최신순."""
    personal, core = _accounts(session, participant_id)
    account_ids = [a.account_id for a in (personal, core) if a is not None]

    from sqlalchemy import or_
    scope = [_E.participant_id == participant_id]
    if account_ids:
        scope.append(_E.account_id.in_(account_ids))
    scope.append(_E.event_type.in_(list(SYSTEM_ALERT_TYPES)))
    stmt = (select(_E)
            .where(_E.event_type.in_(list(ALERT_RULES)))
            .where(or_(*scope))
            .order_by(_E.timestamp.desc(), _E.event_id.desc()))
    rows = list(session.scalars(stmt))

    items = [a for a in (_alert_from_event(e) for e in rows) if a is not None]

    # 이벤트로 남지 않는 상태성 알림: 가격 지연.
    st = status(session, participant_id)
    if st["data_freshness"] == "STALE":
        items.insert(0, {
            "alert_id": f"STALE-{st['latest_price_date']}",
            "type": "PRICE_STALE",
            "date": st["latest_price_date"],
            "occurred_at": None,
            "title": "가격 데이터가 지연되었습니다",
            "detail": {"latest_price_date": st["latest_price_date"],
                       "stale_price_days": st["stale_price_days"]},
            "severity": "warning",
        })

    total = len(items)
    return {"items": items[offset:offset + limit], "total": total,
            "limit": limit, "offset": offset}
