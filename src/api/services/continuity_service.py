"""Owner-only continuous paper NAV, with an explicit historical/forward boundary."""
from copy import deepcopy
from datetime import date
import math
from sqlalchemy import select
from ...db.models.account import Account
from ...db.models.decision import PortfolioDecision
from ...db.models.event import Event
from ...db.models.nav import NavDaily
from ...db.models.holding import Holding
from ...db.models.price import PriceDaily
from ...forward.runtime import kst_today
from ...forward.opening import EVENT


def own(session, participant_id, user_id):
    accounts = list(session.scalars(select(Account).where(Account.participant_id == participant_id)))
    personal = next((a for a in accounts if a.account_type == "personal"), None)
    core = next((a for a in accounts if a.account_type == "core"), None)
    if personal is None or core is None:
        return {"available": False}
    openings = {}
    for account in (personal, core):
        rows = list(session.scalars(select(Event).where(Event.event_type == EVENT,
                    Event.account_id == account.account_id, Event.participant_id == participant_id)))
        if len(rows) != 1:
            return {"available": False}
        openings[account.account_id] = rows[0].payload_json
    initial = openings[personal.account_id]
    benchmark = openings[core.account_id]
    decision = session.get(PortfolioDecision, initial.get("decision_id"))
    if decision is None or decision.user_id != user_id or decision.account_id != personal.account_id:
        return {"available": False}
    if initial["run_id"] != benchmark["run_id"] or initial["forward_start"] != benchmark["forward_start"]:
        return {"available": False}
    archives = session.scalars(select(Event).where(Event.event_type == "HISTORICAL_REPLAY_ARCHIVED",
                Event.account_id == personal.account_id, Event.participant_id == participant_id))
    archive = next((e.payload_json for e in archives if e.payload_json.get("run_id") == initial["run_id"]), None)
    if not archive or archive.get("decision_id") != decision.decision_id:
        return {"available": False}
    start = initial["forward_start"]
    series = [{**p, "data_kind": "HISTORICAL_REPLAY"} for p in deepcopy(archive["series"]) if p["date"] < start]
    if not series:
        return {"available": False}
    series.sort(key=lambda p: p["date"])
    if (len({p["date"] for p in series}) != len(series)
            or any(not positive(p.get(k)) for p in series for k in ("personal_nav", "core_nav"))
            or not math.isclose(series[-1]["personal_nav"], initial["nav"], abs_tol=.01)
            or not math.isclose(series[-1]["core_nav"], benchmark["nav"], abs_tol=.01)):
        return {"available": False}
    base_p, base_c = series[0]["personal_nav"], series[0]["core_nav"]
    for p in series:
        p.update(personal_index=p["personal_nav"] / base_p * 100,
                 core_index=p["core_nav"] / base_c * 100, valid=True)
    by_account = {}
    for account in (personal, core):
        by_account[account.account_id] = {str(n.date): n for n in session.scalars(select(NavDaily).where(
            NavDaily.account_id == account.account_id, NavDaily.date >= date.fromisoformat(start), NavDaily.date <= kst_today()))}
    personal_nav, core_nav = by_account[personal.account_id], by_account[core.account_id]
    holdings = {}
    for h in session.scalars(select(Holding).where(Holding.account_id.in_(by_account),
            Holding.date >= date.fromisoformat(start), Holding.date <= kst_today())):
        holdings.setdefault((h.account_id, str(h.date)), []).append(dict(
            asset_id=h.asset_id, quantity=float(h.quantity), price=float(h.price),
            market_value=float(h.market_value), weight=float(h.weight)))
    evidence = {}
    for event in session.scalars(select(Event).where(Event.event_type == "NAV_CALCULATED", Event.account_id.in_([personal.account_id, core.account_id]))):
        payload = event.payload_json or {}
        key = (event.account_id, payload.get("date"))
        evidence.setdefault(key, []).append(payload.get("data_kind") == "FORWARD_SIMULATION" and payload.get("opening_run_id") == initial["run_id"] and positive(payload.get("nav"))
            and (n := by_account[event.account_id].get(payload.get("date"))) is not None
            and math.isclose(float(payload["nav"]), float(n.nav), rel_tol=1e-8))
    forward_count = 0
    # A stored investable price date with neither NAV is still a visible gap.
    # No weekend rows or fabricated values are added to either ledger.
    assets = {h["asset_id"] for o in (initial, benchmark) for h in o["holdings"]}
    assets.update(h["asset_id"] for rows in holdings.values() for h in rows)
    price_dates = {str(d) for d in session.scalars(select(PriceDaily.date).where(
        PriceDaily.asset_id.in_(assets), PriceDaily.date >= date.fromisoformat(start),
        PriceDaily.date <= kst_today()).distinct())}
    for day in sorted(set(personal_nav) | set(core_nav) | price_dates):
        p, c = personal_nav.get(day), core_nav.get(day)
        valid = p is not None and c is not None and p.nav_status == c.nav_status == "OK" and not p.stale_price_flag and not c.stale_price_flag and p.benchmark_version == c.benchmark_version
        valid = valid and all(positive(n.nav) and math.isfinite(float(n.cash_balance))
            and math.isclose(float(n.nav), float(n.cash_balance) + sum(h["market_value"]
                for h in holdings.get((n.account_id, day), [])), rel_tol=1e-8, abs_tol=.01) for n in (p, c))
        valid = valid and all(evidence.get((a.account_id, day)) and all(evidence[(a.account_id, day)]) for a in (personal, core))
        if valid:
            forward_count += 1
        # A missing/invalid paired observation is a gap, never a fabricated close.
        series.append(dict(date=day, personal_nav=float(p.nav) if valid else None, core_nav=float(c.nav) if valid else None,
            personal_index=float(p.nav) / base_p * 100 if valid else None,
            core_index=float(c.nav) / base_c * 100 if valid else None, data_kind="FORWARD_SIMULATION", valid=valid))
    latest = next(p for p in reversed(series) if p["valid"])
    current = personal_nav.get(latest["date"]) if latest["data_kind"] == "FORWARD_SIMULATION" else None
    snapshot = dict(date=latest["date"], nav=latest["personal_nav"],
        cash_balance=float(current.cash_balance) if current else initial["cash_balance"],
        holdings=holdings.get((personal.account_id, latest["date"]), []) if current else deepcopy(initial["holdings"]))
    summary = dict(start=series[0]["date"], end=latest["date"], observations=sum(p["valid"] for p in series),
        personal_return=latest["personal_nav"] / base_p - 1,
        core_return=latest["core_nav"] / base_c - 1,
        difference_pp=latest["personal_nav"] / base_p - latest["core_nav"] / base_c,
        missing_observations=sum(not p["valid"] for p in series))
    return dict(summary=summary, snapshot=snapshot, available=True, kind="REPLAY_THEN_FORWARD_SIMULATION", historical_start=initial["historical_start"],
        historical_end=initial["historical_end"], forward_start=start, opening=deepcopy(initial),
        decision_confirmed_at=decision.confirmed_at.isoformat(), forward_observations=forward_count, series=series,
        status="FORWARD_OBSERVED" if forward_count else "AWAITING_FORWARD_VALUATION")


def positive(value):
    try:
        return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False
