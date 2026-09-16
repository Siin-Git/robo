"""Participant application service (delegates identity rules to domain)."""
from __future__ import annotations

from ...db.repositories.forward import AccountRepository, ParticipantRepository
from ..errors import ApiError, not_found
from . import _common as C


def _cfg():
    return C.load_forward_cfg()["forward_test"]


def create(session, display_name: str) -> dict:
    ft = _cfg()
    join = C.now_utc().date()
    pid = C.new_id(session, "P", 3)
    ParticipantRepository(session).add(
        participant_id=pid, display_name=display_name, status="active",
        join_date=join, leave_date=None, created_at=C.now_utc(), updated_at=C.now_utc())
    C.log_event(session, "PARTICIPANT_CREATED", ft["benchmark_version"],
                participant_id=pid,
                payload={"display_name": display_name, "join_date": str(join)})
    accounts = AccountRepository(session)
    core_id, pers_id = f"A-{pid}-CORE", f"A-{pid}-PERSONAL"
    for aid, atype in ((core_id, "core"), (pers_id, "personal")):
        accounts.add(account_id=aid, participant_id=pid, account_type=atype,
                     shadow_name=None, benchmark_version=ft["benchmark_version"],
                     inception_date=join, initial_capital_krw=ft["initial_capital_krw"],
                     status="active", created_at=C.now_utc())
        C.log_event(session, "ACCOUNT_CREATED", ft["benchmark_version"],
                    participant_id=pid, account_id=aid,
                    payload={"account_type": atype, "inception_date": str(join)})
    # Record initial core targets (order creation stays with the daily engine,
    # honoring the live pre-launch gate).
    frozen_w, _ = C.frozen_bundle()
    from ...db.repositories.forward import TargetRepository
    targets = TargetRepository(session)
    for aid in (core_id, pers_id):
        targets.record(target_id=C.new_id(session, "G"), account_id=aid,
                       effective_date=join, kind="core", weights_json=dict(frozen_w),
                       core_version=ft["benchmark_version"],
                       theme_universe_version=ft["theme_universe_version"],
                       risk_model_version=ft["risk_model_version"],
                       created_at=C.now_utc())
        C.log_event(session, "PORTFOLIO_GENERATED", ft["benchmark_version"],
                    participant_id=pid, account_id=aid,
                    payload={"kind": "core", "effective_date": str(join)})
    return get(session, pid)


def get(session, participant_id: str) -> dict:
    row = ParticipantRepository(session).get(participant_id)
    if row is None:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")
    return _out(row)


def list(session, status: str | None, limit: int, offset: int) -> tuple[list[dict], int]:
    rows = ParticipantRepository(session).list(status)
    total = len(rows)
    return [_out(r) for r in rows[offset:offset + limit]], total


def set_status(session, participant_id: str, active: bool) -> dict:
    repo = ParticipantRepository(session)
    row = repo.get(participant_id)
    if row is None:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")
    ft = _cfg()
    if active:
        repo.set_status(participant_id, "active", leave_date=None, updated_at=C.now_utc())
        C.log_event(session, "PARTICIPANT_REACTIVATED", ft["benchmark_version"],
                    participant_id=participant_id)
    else:
        today = C.now_utc().date()
        repo.set_status(participant_id, "inactive", leave_date=today, updated_at=C.now_utc())
        C.log_event(session, "PARTICIPANT_DEACTIVATED", ft["benchmark_version"],
                    participant_id=participant_id, payload={"leave_date": str(today)})
    session.flush()
    return get(session, participant_id)


def _out(r) -> dict:
    return {"participant_id": r.participant_id, "display_name": r.display_name,
            "status": r.status, "join_date": C.as_date(r.join_date),
            "leave_date": C.as_date(r.leave_date),
            "created_at": C.as_aware_utc(r.created_at),
            "updated_at": C.as_aware_utc(r.updated_at)}


def require_active(session, participant_id: str):
    row = ParticipantRepository(session).get(participant_id)
    if row is None:
        raise not_found("PARTICIPANT_NOT_FOUND", f"Unknown participant {participant_id}.")
    if row.status != "active":
        raise ApiError("PARTICIPANT_INACTIVE",
                       f"Participant {participant_id} is not active.", 409)
    return row
