"""Participant management: dynamic count, soft-deactivate, reactivation."""
from __future__ import annotations

import sqlite3

from .db import log_event, next_id, now_iso


def add_participant(con: sqlite3.Connection, display_name: str, join_date: str,
                    model_version: str) -> str:
    pid = next_id(con, "P")
    ts = now_iso()
    con.execute(
        "INSERT INTO participants (participant_id, display_name, status, join_date,"
        " leave_date, created_at, updated_at) VALUES (?, ?, 'active', ?, NULL, ?, ?)",
        (pid, display_name, join_date, ts, ts),
    )
    log_event(con, "PARTICIPANT_CREATED", model_version, participant_id=pid,
              payload={"display_name": display_name, "join_date": join_date})
    con.commit()
    return pid


def deactivate_participant(con: sqlite3.Connection, participant_id: str,
                           leave_date: str, model_version: str) -> None:
    cur = con.execute("SELECT status FROM participants WHERE participant_id = ?",
                      (participant_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"unknown participant {participant_id}")
    con.execute("UPDATE participants SET status = 'inactive', leave_date = ?, updated_at = ?"
                " WHERE participant_id = ?", (leave_date, now_iso(), participant_id))
    log_event(con, "PARTICIPANT_DEACTIVATED", model_version, participant_id=participant_id,
              payload={"leave_date": leave_date})
    con.commit()


def reactivate_participant(con: sqlite3.Connection, participant_id: str,
                           model_version: str) -> None:
    cur = con.execute("SELECT status FROM participants WHERE participant_id = ?",
                      (participant_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"unknown participant {participant_id}")
    con.execute("UPDATE participants SET status = 'active', leave_date = NULL, updated_at = ?"
                " WHERE participant_id = ?", (now_iso(), participant_id))
    log_event(con, "PARTICIPANT_REACTIVATED", model_version, participant_id=participant_id)
    con.commit()


def list_participants(con: sqlite3.Connection, status: str | None = None) -> list[dict]:
    q = "SELECT * FROM participants"
    args: tuple = ()
    if status:
        q += " WHERE status = ?"
        args = (status,)
    q += " ORDER BY participant_id"
    return [dict(r) for r in con.execute(q, args).fetchall()]


def get_participant(con: sqlite3.Connection, participant_id: str) -> dict:
    row = con.execute("SELECT * FROM participants WHERE participant_id = ?",
                      (participant_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown participant {participant_id}")
    return dict(row)


def require_active(con: sqlite3.Connection, participant_id: str) -> dict:
    p = get_participant(con, participant_id)
    if p["status"] != "active":
        raise ValueError(f"participant {participant_id} is not active")
    return p


if __name__ == "__main__":
    from .participants_cli import main as _main
    raise SystemExit(_main())
