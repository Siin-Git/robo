"""Owner-only continuous paper NAV, with an explicit historical/forward boundary."""
from copy import deepcopy
from datetime import date
from sqlalchemy import select
from ...db.models.account import Account
from ...db.models.decision import PortfolioDecision
from ...db.models.event import Event
from ...db.models.nav import NavDaily
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
    base_p, base_c = series[0]["personal_nav"], series[0]["core_nav"]
    by_account = {}
    for account in (personal, core):
        by_account[account.account_id] = {str(n.date): n for n in session.scalars(select(NavDaily).where(
            NavDaily.account_id == account.account_id, NavDaily.date >= date.fromisoformat(start)))}
    personal_nav, core_nav = by_account[personal.account_id], by_account[core.account_id]
    evidence = {}
    for event in session.scalars(select(Event).where(Event.event_type == "NAV_CALCULATED", Event.account_id.in_([personal.account_id, core.account_id]))):
        payload = event.payload_json or {}
        key = (event.account_id, payload.get("date"))
        evidence.setdefault(key, []).append(payload.get("data_kind") == "FORWARD_SIMULATION" and payload.get("opening_run_id") == initial["run_id"])
    forward_count = 0
    for day in sorted(set(personal_nav) | set(core_nav)):
        p, c = personal_nav.get(day), core_nav.get(day)
        valid = p is not None and c is not None and p.nav_status == c.nav_status == "OK" and not p.stale_price_flag and not c.stale_price_flag and p.benchmark_version == c.benchmark_version
        valid = valid and all(evidence.get((a.account_id, day)) and all(evidence[(a.account_id, day)]) for a in (personal, core))
        if valid:
            forward_count += 1
        # A missing/invalid paired observation is a gap, never a fabricated close.
        series.append(dict(date=day, personal_nav=float(p.nav) if valid else None, core_nav=float(c.nav) if valid else None,
            personal_index=float(p.nav) / base_p * 100 if valid else None,
            core_index=float(c.nav) / base_c * 100 if valid else None, data_kind="FORWARD_SIMULATION", valid=valid))
    return dict(available=True, kind="REPLAY_THEN_FORWARD_SIMULATION", historical_start=initial["historical_start"],
        historical_end=initial["historical_end"], forward_start=start, opening=deepcopy(initial),
        decision_confirmed_at=decision.confirmed_at.isoformat(), forward_observations=forward_count, series=series,
        status="FORWARD_OBSERVED" if forward_count else "AWAITING_FORWARD_VALUATION")
