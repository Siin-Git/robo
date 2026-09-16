"""Canonical forward-test lifecycle state (single source of truth).

Keys:
  forward_test_inception_at : launch timestamp (Asia/Seoul, offset-aware) or NULL
  first_execution_at        : first paper-trade execution date or NULL

NULL means "not started" and is a VALID state, never an error. History rows
are never updated in place: set-once semantics, enforced here.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

KEYS = ("forward_test_inception_at", "first_execution_at")


def ensure_state_table(con: sqlite3.Connection) -> None:
    con.execute("CREATE TABLE IF NOT EXISTS forward_state ("
                " key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    con.commit()


def get_state(con: sqlite3.Connection, key: str) -> str | None:
    if key not in KEYS:
        raise ValueError(f"unknown state key {key!r}")
    ensure_state_table(con)
    row = con.execute("SELECT value FROM forward_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_state_once(con: sqlite3.Connection, key: str, value: str) -> str:
    """Insert only; raises if already set (no overwrites, ever)."""
    if key not in KEYS:
        raise ValueError(f"unknown state key {key!r}")
    ensure_state_table(con)
    if get_state(con, key) is not None:
        raise RuntimeError(f"{key} is already set; refusing overwrite")
    con.execute("INSERT INTO forward_state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, datetime.now(timezone.utc).isoformat()))
    con.commit()
    return value


def now_seoul_iso() -> str:
    return datetime.now(KST).isoformat()


def live_orders_blocked(con: sqlite3.Connection) -> tuple[bool, str]:
    """True when running live pre-launch: no orders may be created or filled."""
    from .runtime import get_runtime_profile
    if get_runtime_profile() != "live":
        return False, ""
    if get_state(con, "forward_test_inception_at") is None:
        return True, "forward test not launched (forward_test_inception_at is NULL)"
    return False, ""


def canonical_dates(con: sqlite3.Connection, frozen_meta: dict) -> dict:
    """The four canonical dates. Missing lifecycle values are None (NOT STARTED)."""
    return {
        "benchmark_model_date": (frozen_meta.get("run_timestamp", "") or "")[:10],
        "benchmark_snapshot_date": frozen_meta.get("data_end"),
        "forward_test_inception_at": get_state(con, "forward_test_inception_at"),
        "first_execution_at": get_state(con, "first_execution_at"),
    }


def check_invariants(d: dict) -> list[str]:
    """Return list of violations (empty = all hold)."""
    bad = []
    if d["benchmark_model_date"] and d["benchmark_snapshot_date"]:
        if d["benchmark_snapshot_date"] > d["benchmark_model_date"]:
            bad.append("benchmark_snapshot_date > benchmark_model_date")
    if d["forward_test_inception_at"] is not None and d["benchmark_model_date"]:
        if d["forward_test_inception_at"][:10] < d["benchmark_model_date"]:
            bad.append("forward_test_inception_at < benchmark_model_date")
    if d["first_execution_at"] is not None:
        if d["forward_test_inception_at"] is None:
            bad.append("first_execution_at set without inception")
        elif d["first_execution_at"] < d["forward_test_inception_at"][:10]:
            bad.append("first_execution_at < forward_test_inception_at")
    return bad
