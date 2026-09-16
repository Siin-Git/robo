"""Weekly views: submit / hold / close with cutoff and effective dating.

No retroactive application: execution engines only use prices strictly after
effective_at. All timestamps stored as UTC ISO; cutoff evaluated in Asia/Seoul.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from .db import log_event, next_id
from .participants import require_active
from .themes import require_tradable

KST = timezone(timedelta(hours=9))
STATUSES = ("new", "hold", "closed", "rejected")


def parse_ts(ts: str) -> datetime:
    d = datetime.fromisoformat(ts)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def friday_of_week(d) -> str:
    # d: date; return Friday date (ISO) of its Mon-Sun week.
    wd = d.weekday()
    fri = d + timedelta(days=(4 - wd))
    return fri.isoformat()


def next_weekday(date_iso: str) -> str:
    from datetime import date as _date
    d = _date.fromisoformat(date_iso) + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.isoformat()


def cutoff_info(submitted_at: str, cutoff_time: str = "18:00") -> tuple[str, bool]:
    """Legacy alias of resolve_view_schedule (cycle_date, late)."""
    s = resolve_view_schedule(submitted_at, cutoff_time)
    return s["cycle_date"], s["late"]


def resolve_view_schedule(submitted_at: str, cutoff_time: str = "18:00") -> dict:
    """Canonical view-date resolver. Called ONLY at view creation.

    - On-time (<= Friday 18:00 KST): cycle_date = this Friday,
      effective_at = next weekday after submission.
    - Late/weekend: cycle_date = next Friday,
      effective_at = next weekday after that Friday (usually Monday).
    Downstream modules must read DB effective_at, never recompute it.
    """
    kst = parse_ts(submitted_at).astimezone(KST)
    fri = friday_of_week(kst.date())
    cutoff_dt = datetime.fromisoformat(f"{fri}T{cutoff_time}:00+09:00")
    if kst <= cutoff_dt:
        return {"cycle_date": fri,
                "effective_at": next_weekday(kst.date().isoformat()),
                "late": False}
    nxt_fri = (datetime.fromisoformat(fri).date() + timedelta(days=7)).isoformat()
    return {"cycle_date": nxt_fri, "effective_at": next_weekday(nxt_fri), "late": True}


def active_views(con: sqlite3.Connection, participant_id: str) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT * FROM views WHERE participant_id = ? AND status IN ('new','hold')"
        " AND end_at IS NULL ORDER BY submitted_at", (participant_id,)).fetchall()]


def submit_view(con: sqlite3.Connection, participant_id: str, theme_id: str,
                submitted_at: str, reason: str, theme_universe_version: str,
                model_version: str, max_active_themes: int = 2,
                cutoff_time: str = "18:00") -> dict:
    require_active(con, participant_id)
    require_tradable(con, theme_id)
    sched = resolve_view_schedule(submitted_at, cutoff_time)
    cycle_week = sched["cycle_date"]
    late = sched["late"]
    current = active_views(con, participant_id)
    current_themes = {v["theme_id"] for v in current}
    if theme_id in current_themes:
        status = "hold"  # reaffirmation, no state change otherwise
    else:
        if len(current_themes) >= max_active_themes:
            vid = next_id(con, "V")
            con.execute(
                "INSERT INTO views (view_id, participant_id, theme_id, status, submitted_at,"
                " effective_at, end_at, reason, theme_universe_version, cycle_week, cycle_date)"
                " VALUES (?, ?, ?, 'rejected', ?, ?, NULL, ?, ?, ?, ?)",
                (vid, participant_id, theme_id, submitted_at, submitted_at,
                 reason, theme_universe_version, cycle_week, sched["cycle_date"]))
            log_event(con, "VIEW_REJECTED", model_version, participant_id=participant_id,
                      payload={"view_id": vid, "theme_id": theme_id, "reason": "max themes exceeded"})
            con.commit()
            return {"view_id": vid, "status": "rejected", "cycle_week": cycle_week,
                    "cycle_date": sched["cycle_date"], "late": late}
        status = "new"
    # Canonical dates come ONLY from the resolver (single source of truth).
    effective_at = sched["effective_at"]
    cycle_date = sched["cycle_date"]
    vid = next_id(con, "V")
    con.execute(
        "INSERT INTO views (view_id, participant_id, theme_id, status, submitted_at,"
        " effective_at, end_at, reason, theme_universe_version, cycle_week, cycle_date)"
        " VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)",
        (vid, participant_id, theme_id, status, submitted_at, effective_at,
         reason, theme_universe_version, cycle_week, cycle_date))
    log_event(con, "VIEW_SUBMITTED", model_version, participant_id=participant_id,
              payload={"view_id": vid, "theme_id": theme_id, "status": status,
                       "cycle_date": cycle_date, "late": late, "effective_at": effective_at})
    con.commit()
    return {"view_id": vid, "status": status, "cycle_week": cycle_week,
            "cycle_date": cycle_date, "late": late, "effective_at": effective_at}


def close_view(con: sqlite3.Connection, participant_id: str, theme_id: str,
               closed_at: str, model_version: str) -> dict:
    rows = [v for v in active_views(con, participant_id) if v["theme_id"] == theme_id]
    if not rows:
        raise ValueError(f"no active view on {theme_id} for {participant_id}")
    for v in rows:
        con.execute("UPDATE views SET status = 'closed', end_at = ? WHERE view_id = ?",
                    (closed_at, v["view_id"]))
    log_event(con, "VIEW_CLOSED", model_version, participant_id=participant_id,
              payload={"theme_id": theme_id, "closed_at": closed_at,
                       "view_ids": [v["view_id"] for v in rows]})
    con.commit()
    return {"theme_id": theme_id, "closed": len(rows)}


def mark_held(con: sqlite3.Connection, participant_id: str, cycle_week: str,
              model_version: str) -> int:
    """Log VIEW_HELD for carried views (default hold_existing rule)."""
    n = 0
    for v in active_views(con, participant_id):
        log_event(con, "VIEW_HELD", model_version, participant_id=participant_id,
                  payload={"view_id": v["view_id"], "theme_id": v["theme_id"],
                           "cycle_week": cycle_week})
        n += 1
    con.commit()
    return n


if __name__ == "__main__":
    from .views_cli import main as _main
    raise SystemExit(_main())
