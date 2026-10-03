"""Onboarding draft + preview + complete service (no financial logic duplicated)."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select

from ..errors import ApiError, not_found
from . import _common as C
from .frontier_service import FRONTIER_VERSION, describe_position, find_point, get_frontier
from .portfolio_service import _cov_asof, _tickers, _expected_return, EXPECTED_RETURN_BASIS
from src.forward.config import load_forward_config
from src.forward.portfolio import build_personalized
from src.forward.prices import theme_asset_id

def _now():
    return datetime.now(timezone.utc)

def get_draft(session, user_id: str):
    from ...db.models.onboarding import OnboardingDraft as _OD
    row = session.get(_OD, user_id)
    if row is None or row.completed_at is not None:
        return None
    return {
        "user_id": row.user_id,
        "participant_id": row.participant_id,
        "frontier_id": row.frontier_id,
        "frontier_version": row.frontier_version,
        "theme_ids": list(row.theme_ids_json or []),
        "reason": row.reason,
        "current_step": row.current_step,
    }

def upsert_draft(session, user_id: str, participant_id: str, frontier_id: str | None, theme_ids: list[str] | None, reason: str | None, current_step: str):
    from ...db.models.onboarding import OnboardingDraft as _OD
    row = session.get(_OD, user_id)
    now = _now()
    if row is None:
        row = _OD(
            user_id=user_id,
            participant_id=participant_id,
            frontier_id=frontier_id,
            frontier_version=FRONTIER_VERSION if frontier_id else None,
            theme_ids_json=list(theme_ids or []),
            reason=reason,
            current_step=current_step,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        session.add(row)
    else:
        if row.completed_at is not None:
            row.completed_at = None
        row.participant_id = participant_id
        if frontier_id is not None:
            row.frontier_id = frontier_id
            row.frontier_version = FRONTIER_VERSION
        if theme_ids is not None:
            row.theme_ids_json = list(theme_ids)
        if reason is not None:
            row.reason = reason
        row.current_step = current_step
        row.updated_at = now
    session.flush()
    return get_draft(session, user_id)

def preview(session, user_id: str, participant_id: str, frontier_id: str, theme_ids: list[str]):
    point = find_point(frontier_id)
    if point is None:
        raise not_found("FRONTIER_POINT_NOT_FOUND", f"Unknown frontier_id {frontier_id}.")
    frontier = get_frontier()
    if frontier["frontier_version"] != FRONTIER_VERSION:
        raise ApiError("FRONTIER_VERSION_MISMATCH", "Frontier version mismatch.", 409)
    if len(theme_ids) > 2:
        raise ApiError("VIEW_LIMIT_EXCEEDED", "Maximum 2 themes.", 409)
    if len(set(theme_ids)) != len(theme_ids):
        raise ApiError("DUPLICATE_THEME", "Duplicate themes.", 400)
    from ...db.models.theme import Theme as _T
    for tid in theme_ids:
        t = session.get(_T, tid)
        if t is None:
            raise not_found("THEME_NOT_FOUND", f"Unknown theme {tid}.")
        if not t.active or not t.ticker:
            raise ApiError("THEME_INACTIVE", f"Theme {tid} not tradable.", 422)
    base_weights = {w["asset_id"]: w["weight"] for w in point["weights"]}
    if "cash" not in base_weights:
        base_weights["cash"] = 0.0

    from ...db.models.price import PriceDaily as _Px
    latest = session.scalars(select(_Px.date).order_by(_Px.date.desc())).first()
    from . import market_comparison
    if market_comparison.enabled():
        latest = market_comparison.price_date()
    theme_asset_ids = [theme_asset_id(t) for t in theme_ids]
    comparison_base_vol = None
    risk_limit_pp = None

    if latest is None:
        personalized_weights = dict(base_weights)
        # inject theme placeholders at target weights for preview
        if theme_ids:
            # fallback without cov: use target weights directly
            try:
                cfg = load_forward_config()
                from src.forward.portfolio import theme_target_weights, fund_from_equities
                tw = theme_target_weights(theme_ids, cfg)
                base_core, funding_dummy = fund_from_equities(base_weights, {theme_asset_id(k): v for k, v in tw.items()})
                personalized_weights = dict(base_core)
                for k, v in tw.items():
                    personalized_weights[theme_asset_id(k)] = v
                funding = funding_dummy
                pers_vol = None
                pers_te = None
                risk_applied = False
            except Exception:
                funding = {}
                pers_vol = None
                pers_te = None
                risk_applied = False
        else:
            funding = {}
            pers_vol = None
            pers_te = None
            risk_applied = False
    else:
        asset_ids = [a for a in base_weights if a != "cash"] + theme_asset_ids
        cov = _cov_asof(session, asset_ids, latest)
        if cov is None:
            # same fallback as above
            try:
                cfg = load_forward_config()
                from src.forward.portfolio import theme_target_weights, fund_from_equities
                tw = theme_target_weights(theme_ids, cfg)
                base_core, funding_dummy = fund_from_equities(base_weights, {theme_asset_id(k): v for k, v in tw.items()})
                personalized_weights = dict(base_core)
                for k, v in tw.items():
                    personalized_weights[theme_asset_id(k)] = v
                funding = funding_dummy
                pers_vol = None
                pers_te = None
                risk_applied = False
            except Exception:
                personalized_weights = dict(base_weights)
                funding = {}
                pers_vol = None
                pers_te = None
                risk_applied = False
        else:
            cfg = load_forward_config()
            res = build_personalized(base_weights, theme_asset_ids, cfg, cov)
            personalized_weights = res["weights"]
            funding = res.get("funding", {})
            risk_applied = res.get("scaled", False)
            pers_vol = res.get("vol")
            pers_te = res.get("te")
            comparison_base_vol = res.get("core_vol")
            risk_limit_pp = float(cfg["forward_test"]["risk_guardrail"]["max_vol_increase_pp"])

    def groups_for(weights: dict):
        eq = sum(weights.get(a, 0) for a in ["us_equity", "developed_ex_us", "emerging_markets", "korea_equity"])
        fi = sum(weights.get(a, 0) for a in ["us_treasury", "korea_treasury", "tips"])
        alt = sum(weights.get(a, 0) for a in ["gold", "global_reit"])
        cash = weights.get("cash", 0)
        themes_sum = sum(v for k, v in weights.items() if k.startswith("theme:"))
        broad_eq = float(eq)
        return {"equity": float(eq), "fixed_income": float(fi), "alternatives": float(alt), "cash": float(cash), "broad_equity": float(broad_eq), "themes": float(themes_sum)}

    tickers = _tickers(session)
    base_groups = groups_for(base_weights)
    pers_groups = groups_for(personalized_weights)

    active = []
    for aid in sorted(set(base_weights) | set(personalized_weights)):
        d = personalized_weights.get(aid, 0) - base_weights.get(aid, 0)
        if abs(d) > 1e-9:
            disp = aid.split(":", 1)[1] if aid.startswith("theme:") else aid
            active.append({"asset_id": disp, "weight": float(d), "asset_type": "active", "ticker": tickers.get(disp) if disp in tickers else None})

    # Guardrail scaling returns some funding to core assets. Report the final
    # reductions, not the amounts originally requested before scaling.
    funding_list = [
        {"asset_id": k, "weight": float(v - personalized_weights.get(k, 0.0))}
        for k, v in base_weights.items()
        if v - personalized_weights.get(k, 0.0) > 1e-9
    ]
    themes_info = []
    for tid in theme_ids:
        t = session.get(_T, tid)
        tw = personalized_weights.get(f"theme:{tid}", 0)
        themes_info.append({"theme_id": tid, "display_name": t.display_name if t else tid, "ticker": t.ticker if t else None, "target_weight": float(tw)})

    expected_return = _expected_return(personalized_weights, base_weights)
    frontier_position = {
        "base": describe_position(
            frontier_id=frontier_id,
            label="base",
        ),
        "personalized": describe_position(
            volatility=pers_vol,
            expected_return=expected_return,
            label="personalized",
        ),
    }

    return {
        "base": {"frontier_id": frontier_id, "expected_return": float(point["expected_return"]), "volatility": float(point["volatility"]), "weights": [{"asset_id": k, "weight": float(v)} for k, v in base_weights.items()], "groups": base_groups},
        "themes": themes_info,
        "personalized": {"expected_return": expected_return, "expected_return_basis": EXPECTED_RETURN_BASIS, "volatility": pers_vol, "tracking_error": pers_te, "weights": [{"asset_id": k, "weight": float(v)} for k, v in personalized_weights.items()], "groups": pers_groups},
        "comparison": active,
        "funding": funding_list,
        "frontier_position": frontier_position,
        "risk_guardrail_applied": bool(risk_applied),
        "risk_comparison": {
            "base_volatility": comparison_base_vol,
            "personalized_volatility": pers_vol,
            "max_increase_pp": risk_limit_pp,
            "as_of": latest.isoformat() if latest is not None else None,
            "method": "5Y weekly Ledoit-Wolf" if comparison_base_vol is not None else None,
        },
    }

def complete(session, user_id: str, participant_id: str, frontier_id: str, theme_ids: list[str], reason: str | None, adjustment_choice_id: str | None = None, confirmed_preview: dict | None = None, expected_decision_id: str | None = None):
    from . import decision_service as decisions
    from ...db.models.account import Account as _A
    acc = session.scalars(select(_A).where(_A.participant_id == participant_id, _A.account_type == "personal")).first()
    if acc:
        decisions.lock_account(session, acc.account_id)
    prev = confirmed_preview if confirmed_preview is not None else preview(session, user_id, participant_id, frontier_id, theme_ids)
    from ...db.models.base_selection import BasePortfolioSelection as _BPS
    from ...db.models.onboarding import OnboardingDraft as _OD
    existing = session.scalars(select(_BPS).where(_BPS.user_id == user_id, _BPS.status == "active").order_by(_BPS.selected_at.desc())).first()
    if existing and existing.frontier_id == frontier_id:
        from ...db.models.view import View as _V
        cur_themes = sorted([v.theme_id for v in session.scalars(select(_V).where(_V.participant_id == participant_id, _V.status.in_(["new", "hold"]), _V.end_at.is_(None))).all()])
        previous_draft = session.get(_OD, user_id)
        if sorted(theme_ids) == cur_themes and previous_draft and previous_draft.completed_at and previous_draft.reason == reason:
            d = decisions.latest(session, acc.account_id) if acc else None
            if d and not adjustment_choice_id:
                return {"already_completed": True, "selection_id": existing.selection_id, "decision_id": d.decision_id}
            if d and adjustment_choice_id and d.provenance_json.get("adjustment_choice_id") == adjustment_choice_id:
                return {"already_completed": True, "selection_id": existing.selection_id, "decision_id": d.decision_id}
    from ...db.models.account import Account as _A
    from ...db.models.portfolio import PortfolioTarget as _PT
    now = C.now_utc()
    if acc:
        current = decisions.latest(session, acc.account_id)
        if expected_decision_id and (not current or current.decision_id != expected_decision_id):
            raise ApiError("STALE_DECISION", "다른 확정이 이루어졌습니다. 최신 판단에서 다시 설계해 주세요.", 409)
        decisions.validate_adjustment(session, user_id, acc.account_id, adjustment_choice_id)
        decisions.check_pending(session, acc.account_id)
    effective = decisions.effective_day(now)
    for r in session.scalars(select(_BPS).where(_BPS.user_id == user_id, _BPS.status == "active")).all():
        r.status = "superseded"
    sel_id = C.new_id(session, "BP", 3)
    point = find_point(frontier_id) or {**prev["base"], "sharpe": None}
    weights = {w["asset_id"]: w["weight"] for w in point["weights"]}
    if "cash" not in weights:
        weights["cash"] = 0.0
    row = _BPS(
        selection_id=sel_id,
        user_id=user_id,
        participant_id=participant_id,
        frontier_version=FRONTIER_VERSION,
        frontier_id=frontier_id,
        expected_return=point["expected_return"],
        volatility=point["volatility"],
        sharpe=point["sharpe"],
        weights_json=weights,
        selected_at=now,
        effective_at=datetime.combine(effective, datetime.min.time(), tzinfo=timezone.utc),
        status="active",
    )
    session.add(row)
    acc = session.scalars(select(_A).where(_A.participant_id == participant_id, _A.account_type == "personal")).first()
    if acc:
        tgt_id = C.new_id(session, "G")
        pers_weights = {w["asset_id"]: w["weight"] for w in prev["personalized"]["weights"]}
        target = _PT(target_id=tgt_id, account_id=acc.account_id, effective_date=effective, kind="decision", weights_json=dict(pers_weights), core_version="CORE_V0.3", theme_universe_version="THEME_UNIVERSE_V0.1", risk_model_version="RISK_5Y_LW_FROZEN_V0", created_at=now)
        session.add(target)
        session.flush()
        decision = decisions.capture(session, user_id, participant_id, acc, target, row, prev, reason, adjustment_choice_id)
    # Close the old choice instead of accumulating every prior Theme as active.
    from ...db.models.view import View as _V
    for view in session.scalars(select(_V).where(_V.participant_id == participant_id,
            _V.end_at.is_(None), _V.status.in_(["new", "hold"]))):
        view.end_at = now
        view.status = "closed"
    if theme_ids:
        from ...forward.views import resolve_view_schedule
        from ...db.models.view import View as _V
        from datetime import date as _date
        for tid in theme_ids:
            vid = C.new_id(session, "V")
            sched = resolve_view_schedule(now.isoformat(), "18:00")
            # For onboarding, make view effective immediately (today) rather than next weekday
            eff = effective
            cycle_d = _date.fromisoformat(sched["cycle_date"])
            session.add(_V(view_id=vid, participant_id=participant_id, theme_id=tid, status="new", submitted_at=now, effective_at=eff, end_at=None, reason=reason or "", theme_universe_version="THEME_UNIVERSE_V0.1", cycle_week=cycle_d, cycle_date=cycle_d))
    draft = session.get(_OD, user_id)
    if draft:
        draft.frontier_id = frontier_id
        draft.frontier_version = FRONTIER_VERSION
        draft.theme_ids_json = list(theme_ids)
        draft.reason = reason
        draft.completed_at = now
        draft.updated_at = now
        draft.current_step = "completed"
    else:
        session.add(_OD(user_id=user_id, participant_id=participant_id, frontier_id=frontier_id, frontier_version=FRONTIER_VERSION, theme_ids_json=list(theme_ids), reason=reason, current_step="completed", created_at=now, updated_at=now, completed_at=now))
    C.log_event(session, "ONBOARDING_COMPLETED", "CORE_V0.3", participant_id=participant_id, payload={"selection_id": sel_id, "frontier_id": frontier_id, "theme_ids": theme_ids, "reason": reason})
    session.flush()
    return {"selection_id": sel_id, "frontier_id": frontier_id, "theme_ids": theme_ids, "decision_id": decision.decision_id if acc else None}
