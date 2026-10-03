"""Reserved demo enrollment. Identity is real; scenario reports are explicitly synthetic.

Only exact catalog combinations can reference an existing public fixture. No NAV
is backfilled into a new user's account and no legacy user's identity is reused.
"""
from copy import deepcopy
from sqlalchemy import select, update, inspect
from ...db.models.demo_cohort import DemoCohort, DemoSlot
from ...db.models.operational import ForwardState
from ...db.models.user import User
from ...db.models.theme import Theme
from ...local.capstone import COHORT, COHORT_SIZE, EMAILS, enabled
from ...forward.portfolio import theme_target_weights, fund_from_equities
from ..errors import ApiError
from . import _common as C, auth_service as auth
from .portfolio_service import _legs, _tickers

ACTIVE_KEY = "demo_active_cohort"


def active(session):
    if not enabled() or not inspect(session.get_bind()).has_table("demo_cohorts"):
        return None
    state = session.get(ForwardState, ACTIVE_KEY)
    return session.get(DemoCohort, state.value) if state and state.value else None


def slots(session, group):
    return list(session.scalars(select(DemoSlot).where(DemoSlot.cohort_id == group.cohort_id)))


def own(session, user):
    if not enabled() or not inspect(session.get_bind()).has_table("demo_slots"):
        return None
    return session.scalar(select(DemoSlot).where(DemoSlot.user_id == user.user_id))


def register(session, email, password, name, invite):
    group = active(session)
    if not group:
        raise ApiError("REGISTRATION_DISABLED", "시연용 초대 슬롯이 준비되지 않았습니다.", 403)
    norm = auth.normalize_email(email)
    # A write is obtained before identity creation and counter allocation. The
    # conditional UPDATE is atomic across connections/processes, not a Python lock.
    slot = session.scalar(select(DemoSlot).where(DemoSlot.cohort_id == group.cohort_id,
        DemoSlot.invite_hash == auth.hash_token(invite or ""), DemoSlot.email_normalized == norm))
    if slot is None:
        if all(s.user_id is not None for s in slots(session, group)):
            raise ApiError("COHORT_FULL", "현재 비교군의 예약 자리가 모두 사용되었습니다.", 409)
        raise ApiError("INVALID_INVITATION", "초대 정보와 예약 이메일을 확인해 주세요.", 403)
    if session.scalar(select(User).where(User.email_normalized == norm)):
        raise ApiError("EMAIL_ALREADY_EXISTS", "이미 가입된 이메일입니다. 로그인해 주세요.", 409)
    if slot.user_id:
        raise ApiError("COHORT_FULL", "이 초대 슬롯은 이미 사용되었습니다.", 409)
    claimed = session.execute(update(DemoSlot).where(DemoSlot.slot_id == slot.slot_id,
        DemoSlot.user_id.is_(None), DemoSlot.invite_hash == auth.hash_token(invite or ""))
        .values(invite_hash=auth.hash_token("claimed:" + (invite or ""))))
    if claimed.rowcount != 1:
        raise ApiError("COHORT_FULL", "이 비교군의 예약 자리가 이미 사용되었습니다.", 409)
    info = auth.register(session, email, password, name)
    slot.user_id = info["user_id"]
    # Keep hash so retry is identified as an existing account, never duplicated.
    slot.invite_hash = auth.hash_token(invite or "")
    session.flush()
    return info


def conditions(session):
    weights, meta = C.frozen_bundle()
    ft = C.load_forward_cfg()["forward_test"]
    from . import market_comparison
    return {"market_comparison": market_comparison.enabled(), "benchmark": ft["benchmark_version"], "core_allocation": _legs(weights, _tickers(session)),
        "target_volatility": meta.get("target_volatility"),
        "selection_basis": meta.get("bl", {}).get("risk_anchor"),
        "risk_method": meta.get("bl", {}).get("primary_covariance"),
        "model_reference_date": ft["model_reference_date"], "initial_nav": ft["initial_nav"],
        "initial_capital_krw": ft["initial_capital_krw"], "costs": ft["costs"],
        "theme_budget": ft["active_sleeve"],
        "scenarios": [{"scenario_id": f"CAPSTONE_{i+1:02d}", "themes": t} for i, (_, t) in enumerate(COHORT)]}


def status(session, user):
    group, slot = active(session), own(session, user)
    counts = slots(session, group) if group else []
    out = {"status": "not_required", "cohort_id": group.cohort_id if group else "legacy",
        "capacity": COHORT_SIZE, "registered": group.prepared_count + sum(s.confirmed_at is not None for s in counts) if group else COHORT_SIZE,
        "reserved": sum(s.confirmed_at is None for s in counts),
        "claimed": sum(s.user_id is not None and s.confirmed_at is None for s in counts)}
    if slot:
        out.update(status="completed" if slot.confirmed_at else "setup_required", draft=slot.draft_json,
            configuration=slot.configuration_json, confirmed_at=slot.confirmed_at,
            forward_started_at=slot.forward_started_at, membership_cohort_id=slot.cohort_id,
            in_active_cohort=bool(group and group.cohort_id == slot.cohort_id))
    from . import market_comparison
    out["market_comparison"] = market_comparison.enabled()
    out["can_reset"] = bool(market_comparison.enabled() and slot and group
        and slot.cohort_id == group.cohort_id and not slot.forward_started_at)
    return out


def latest_reset(session, participant_id):
    from ...db.models.event import Event
    return session.scalar(select(Event).where(Event.participant_id == participant_id,
        Event.event_type == "DEMO_PORTFOLIO_RESET").order_by(Event.timestamp.desc(), Event.event_id.desc()))


def reset_portfolio(session, user):
    """Restart the caller's reserved setup; keep identity, reservation and history."""
    from . import market_comparison
    if not market_comparison.enabled():
        raise ApiError("RESET_NOT_AVAILABLE", "이 환경에서는 포트폴리오 초기화를 지원하지 않습니다.", 403)
    slot = require_slot(session, user)
    session.execute(update(DemoSlot).where(DemoSlot.slot_id == slot.slot_id).values(slot_number=slot.slot_number))
    session.refresh(slot)
    if slot.forward_started_at:
        raise ApiError("RESET_NOT_AVAILABLE", "운용이 시작된 포트폴리오는 초기화할 수 없습니다.", 409)
    C.log_event(session, "DEMO_PORTFOLIO_RESET", "CORE_V0.3", participant_id=user.participant_id,
        payload={"cohort_id": slot.cohort_id, "configuration": slot.configuration_json,
                 "draft": slot.draft_json, "report": slot.report_json})
    slot.configuration_json = None
    slot.report_json = None
    slot.confirmed_at = None
    slot.draft_json = {"core_id": "CORE_V0.3", "theme_ids": [], "reason": "", "current_step": "risk"}
    session.flush()
    return status(session, user)


def validate(session, data, final=False):
    if data.get("core_id") != C.load_forward_cfg()["forward_test"]["benchmark_version"]:
        raise ApiError("COMMON_CORE_REQUIRED", "이번 비교 실험에서는 공통 CORE를 사용합니다.", 422)
    ids = data.get("theme_ids", [])
    if len(ids) > 2 or len(set(ids)) != len(ids):
        raise ApiError("VIEW_LIMIT_EXCEEDED", "Theme은 중복 없이 최대 2개입니다.", 422)
    for tid in ids:
        theme = session.get(Theme, tid)
        if not theme or not theme.active or not theme.ticker:
            raise ApiError("THEME_INACTIVE", "지원하지 않는 Theme입니다.", 422)
    from . import market_comparison
    if data.get("frontier_id"):
        from .frontier_service import find_point
        if not market_comparison.enabled() or find_point(data["frontier_id"]) is None:
            raise ApiError("FRONTIER_POINT_NOT_FOUND", "선택한 위험 수준을 확인해 주세요.", 422)
    if final and not market_comparison.enabled() and not data.get("reason", "").strip():
        raise ApiError("REASON_REQUIRED", "선택 이유를 입력해 주세요.", 422)
    return ids


def require_slot(session, user):
    slot = own(session, user)
    group = active(session)
    if not slot or not group or slot.cohort_id != group.cohort_id:
        raise ApiError("INVITATION_REQUIRED", "현재 비교군의 예약 참가자만 초기 설정할 수 있습니다.", 403)
    return slot


def save_draft(session, user, data):
    slot = require_slot(session, user)
    if slot.confirmed_at:
        raise ApiError("EXPERIMENT_FROZEN", "확정 구성은 변경할 수 없습니다. 자유 설계를 이용하세요.", 409)
    validate(session, data)
    slot.draft_json = dict(data)
    session.flush()
    return status(session, user)


def preview(session, data):
    ids = validate(session, data)
    weights, _ = C.frozen_bundle()
    from . import market_comparison, onboarding_service
    if market_comparison.enabled() and data.get("frontier_id"):
        p = onboarding_service.preview(session, "", "", data["frontier_id"], ids)
        return {**p, "core_id": data["core_id"], "frontier_id": data["frontier_id"],
            "theme_ids": ids, "reason": data.get("reason") or "",
            "allocation": _legs({w["asset_id"]: w["weight"] for w in p["personalized"]["weights"]}, _tickers(session)),
            "core_allocation": _legs(weights, _tickers(session)), "scenario_id": None,
            "performance_status": "MARKET_PRICE_REPLAY", "risk_guardrail_status": "시장 가격 기반 위험 한도 적용"}
    tw = theme_target_weights([f"theme:{t}" for t in ids], C.load_forward_cfg())
    funded, _ = fund_from_equities(weights, tw)
    scenario = next((f"CAPSTONE_{i+1:02d}" for i, (_, t) in enumerate(COHORT) if sorted(t) == sorted(ids)), None)
    def groups(w):
        eq = sum(w.get(a, 0) for a in ("us_equity", "developed_ex_us", "emerging_markets", "korea_equity"))
        return {"equity": eq, "broad_equity": eq,
            "fixed_income": sum(w.get(a, 0) for a in ("us_treasury", "korea_treasury", "tips")),
            "alternatives": sum(w.get(a, 0) for a in ("gold", "global_reit")),
            "cash": w.get("cash", 0), "themes": sum(v for k, v in w.items() if k.startswith("theme:"))}
    final_weights = {**funded, **tw}
    from . import market_comparison
    risk = None
    if market_comparison.enabled():
        from ...forward.portfolio import build_personalized
        assets = [a for a in [*weights, *tw] if a != "cash"]
        risk = build_personalized(weights, list(tw), C.load_forward_cfg(), market_comparison.risk_cov(assets, market_comparison.price_date()))
        final_weights = risk["weights"]
        tw = risk["theme_weights"]
        scenario = None
    tickers = _tickers(session)
    return {"base": {"frontier_id": data["core_id"], "expected_return": None, "volatility": risk["core_vol"] if risk else None,
                "weights": [{"asset_id": k, "weight": v} for k, v in weights.items()], "groups": groups(weights)},
            "personalized": {"volatility": risk["vol"] if risk else None, "tracking_error": risk["te"] if risk else None,
                "weights": [{"asset_id": k, "weight": v} for k, v in final_weights.items()], "groups": groups(final_weights)},
            "themes": [{"theme_id": tid, "ticker": tickers.get(tid), "target_weight": tw.get(f"theme:{tid}", 0)} for tid in ids],
            "risk_guardrail_applied": risk["scaled"] if risk else False,
            "risk_comparison": {"base_volatility": risk["core_vol"], "personalized_volatility": risk["vol"],
                "max_increase_pp": C.load_forward_cfg()["forward_test"]["risk_guardrail"]["max_vol_increase_pp"],
                "as_of": market_comparison.price_date().isoformat(), "method": "5Y weekly Ledoit-Wolf"} if risk else None,
            "core_id": data["core_id"], "theme_ids": ids, "reason": data.get("reason", ""),
        "allocation": _legs(final_weights, _tickers(session)),
        "core_allocation": _legs(weights, _tickers(session)), "scenario_id": scenario,
        "performance_status": "MARKET_PRICE_REPLAY" if risk else "DEMO_SCENARIO" if scenario else "AWAITING_PERFORMANCE",
        "risk_guardrail_status": "시장 가격 기반 위험 한도 적용" if risk else "시연용 고정 목표 비중 · 실제 실행 시 Backend 위험 검증 필요"}


def complete(session, user, data):
    slot = require_slot(session, user)
    # Serialize even when an auth dependency already opened the transaction.
    session.execute(update(DemoSlot).where(DemoSlot.slot_id == slot.slot_id).values(slot_number=slot.slot_number))
    session.refresh(slot)
    if slot.confirmed_at:
        if any(slot.configuration_json.get(k) != data.get(k) for k in ("core_id", "frontier_id", "theme_ids", "reason")):
            raise ApiError("EXPERIMENT_FROZEN", "이미 확정된 실험 구성입니다.", 409)
        return status(session, user)
    validate(session, data, final=True)
    config = preview(session, data)
    report = None
    if config["scenario_id"]:
        from .comparison_service import legacy_detail
        idx = int(config["scenario_id"].split("_")[-1]) - 1
        source = session.scalar(select(User).where(User.email_normalized == EMAILS[idx]))
        if source is None:
            raise ApiError("DEMO_DATA_INCOMPLETE", "선택 조합의 시연 자료가 없습니다.", 409)
        report = deepcopy(legacy_detail(session, source.participant_id))
        if sorted(report["themes"]) != sorted(config["theme_ids"]) or sorted(report["allocation"], key=lambda w: w["asset_id"]) != sorted(config["allocation"], key=lambda w: w["asset_id"]):
            raise ApiError("SCENARIO_MISMATCH", "선택 구성과 시연 시나리오가 일치하지 않습니다.", 409)
        report.update(participant_id=user.participant_id, display_name=user.participant.display_name,
            data_source="DEMO_SCENARIO_ASSIGNED", scenario_id=config["scenario_id"])
    slot.configuration_json = config
    slot.report_json = report
    slot.confirmed_at = C.now_utc()
    slot.draft_json = {**data, "current_step": "completed"}
    # Actual account target starts now. No historical NAV, holdings or trades copied.
    from ...db.models.portfolio import PortfolioTarget
    from ...db.models.account import Account
    acc = session.scalar(select(Account).where(Account.participant_id == user.participant_id, Account.account_type == "personal"))
    ft = C.load_forward_cfg()["forward_test"]
    from ..design_workspace import enabled as design_enabled
    if not design_enabled():
        session.add(PortfolioTarget(target_id=C.new_id(session, "G"), account_id=acc.account_id,
            effective_date=slot.confirmed_at.date(), kind="personal",
            weights_json={(("theme:" + w["asset_id"]) if w["asset_type"] == "theme" else w["asset_id"]): w["weight"] for w in config["allocation"]},
            core_version=ft["benchmark_version"], theme_universe_version=ft["theme_universe_version"],
            risk_model_version=ft["risk_model_version"], created_at=slot.confirmed_at))
    C.log_event(session, "DEMO_CONFIGURATION_CONFIRMED", ft["benchmark_version"], participant_id=user.participant_id,
        payload={"cohort_id": slot.cohort_id, "scenario_id": config["scenario_id"], "theme_ids": config["theme_ids"]})
    session.flush()
    return status(session, user)
