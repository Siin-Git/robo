"""Phase 2.1 launch-hardening tests: profiles, view dates, clean init, no-retroactivity."""
import hashlib
import os
import sqlite3

import pandas as pd
import pytest

from src.forward import runtime as _rt
from src.forward.db import connect, init_db
from src.forward.ledger import valuate
from src.forward.participants import add_participant
from src.forward.prices import upsert_prices
from src.forward.themes import register_themes
from src.forward.views import active_views, resolve_view_schedule, submit_view

THEME_ROWS = {"universe_version": "THEME_UNIVERSE_V0.1", "themes": [
    {"theme_id": "ai", "display_name": "ai", "theme_type": "theme", "ticker": "T",
     "market": "US", "currency": "USD", "active": True, "valid_from": "2022-01-01",
     "valid_to": None, "universe_version": "THEME_UNIVERSE_V0.1"}]}


def test_profile_db_paths_split():
    assert _rt.get_database_path("live").name == "forward_test.db"
    assert _rt.get_database_path("demo").name == "forward_demo.db"
    assert _rt.get_database_path("validation").name == "forward_validation.db"
    with pytest.raises(ValueError):
        _rt.get_database_path("prod")
    assert "PROFILE: LIVE" in _rt.safety_banner("live")
    assert "forward_demo.db" in _rt.safety_banner("demo")


def test_seed_demo_refuses_live(tmp_path, monkeypatch):
    import src.forward.seed_demo as _seed
    monkeypatch.setenv("APP_PROFILE", "live")
    monkeypatch.setattr(_seed, "get_database_path", lambda: tmp_path / "live.db")
    assert _seed.main() == 2
    assert not (tmp_path / "live.db").exists()


def test_view_schedule_cases():
    assert resolve_view_schedule("2026-09-11T08:59:00+00:00") == {
        "cycle_date": "2026-09-11", "effective_at": "2026-09-14", "late": False}
    assert resolve_view_schedule("2026-09-11T09:01:00+00:00") == {
        "cycle_date": "2026-09-18", "effective_at": "2026-09-21", "late": True}
    assert resolve_view_schedule("2026-09-12T00:00:00+00:00") == {
        "cycle_date": "2026-09-18", "effective_at": "2026-09-21", "late": True}
    assert resolve_view_schedule("2026-09-13T12:00:00+00:00") == {
        "cycle_date": "2026-09-18", "effective_at": "2026-09-21", "late": True}
    assert resolve_view_schedule("2026-09-09T00:00:00+00:00") == {
        "cycle_date": "2026-09-11", "effective_at": "2026-09-10", "late": False}


def test_view_stores_canonical_dates(tmp_path):
    con = connect(tmp_path / "v.db")
    init_db(con)
    register_themes(con, THEME_ROWS)
    p = add_participant(con, "A", "2026-09-01", "CORE_V0.3")
    r = submit_view(con, p, "ai", "2026-09-12T00:00:00+00:00", "why",
                    "THEME_UNIVERSE_V0.1", "CORE_V0.3")
    row = active_views(con, p)[0]
    assert (row["cycle_date"], row["effective_at"]) == ("2026-09-18", "2026-09-21")
    assert r["effective_at"] == row["effective_at"]  # single source of truth


def test_holiday_execution_moves_past_effective(tmp_path):
    # Monday 2025-01-13 has NO prices (simulated holiday); effective Monday
    # must still execute Tuesday, never Friday-before.
    from src.forward.execution import create_orders, execute_pending
    from src.forward.prices import next_available_close
    idx = pd.bdate_range("2025-01-10", periods=5)  # Fri..Thu
    panel = pd.DataFrame({"us_equity": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)
    panel = panel.drop(pd.Timestamp("2025-01-13"))  # Monday holiday
    con = connect(tmp_path / "h.db")
    init_db(con)
    upsert_prices(con, panel, "synthetic")
    assert next_available_close(con, "us_equity", "2025-01-13") == "2025-01-14"
    p = add_participant(con, "A", "2025-01-06", "CORE_V0.3")
    from src.forward.accounts import record_target, versions_from_cfg as _vv
    _versions = {"benchmark_version": "CORE_V0.3", "theme_universe_version": "T",
                 "risk_model_version": "R", "execution_rule_version": "E"}
    record_target(con, "A-X", {"us_equity": 0.0, "cash": 1.0}, "2025-01-06", "core",
                  _versions, "CORE_V0.3", p)
    record_target(con, "A-X", {"us_equity": 0.5, "cash": 0.5}, "2025-01-13", "core",
                  _versions, "CORE_V0.3", p)
    create_orders(con, "A-X", {"us_equity": 0.5, "cash": 0.5},
                  "2025-01-10T00:00:00+00:00", "2025-01-13", "CORE_V0.3", p)
    con.execute("INSERT INTO accounts (account_id, participant_id, account_type, shadow_name,"
                " benchmark_version, inception_date, initial_capital_krw, status, created_at)"
                " VALUES ('A-X', ?, 'core', NULL, 'CORE_V0.3', '2025-01-06', 100.0, 'active', 'x')",
                (p,))
    execute_pending(con, "A-X", "2025-01-14", 5, "CORE_V0.3", p)
    got = con.execute("SELECT execution_at FROM trades").fetchone()["execution_at"]
    assert got == "2025-01-14"


def test_clean_init_counts_and_refusal(tmp_path, monkeypatch):
    import src.forward.init_forward_test as _init
    dbp = tmp_path / "fresh.db"
    monkeypatch.setattr(_init, "get_database_path", lambda: dbp)
    # refuse bootstrap network: point snapshot/theme at existing fixtures is heavy;
    # instead verify the refusal gate directly on a dirty DB.
    con = connect(dbp)
    init_db(con)
    con.execute("INSERT INTO participants (participant_id, display_name, status, join_date,"
                " leave_date, created_at, updated_at) VALUES ('P001','X','active','2025-01-01',"
                " NULL,'x','x')")
    con.commit()
    assert _init.main() == 2  # refuses destructive reinit


def test_no_nav_before_first_execution(tmp_path):
    con = connect(tmp_path / "n.db")
    init_db(con)
    con.execute("INSERT INTO accounts (account_id, participant_id, account_type, shadow_name,"
                " benchmark_version, inception_date, initial_capital_krw, status, created_at)"
                " VALUES ('A','P','core',NULL,'CORE_V0.3','2025-01-06',100.0,'active','x')")
    r = valuate(con, "A", "2025-01-10", {"benchmark_version": "V", "theme_universe_version": "T",
                                         "risk_model_version": "R", "execution_rule_version": "E"},
                100.0)
    assert r["status"] == "NAV_INCOMPLETE" and r["reason"] == "no executions yet"
    assert con.execute("SELECT COUNT(*) c FROM nav_daily").fetchone()["c"] == 0


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def test_replay_does_not_touch_live_or_demo_db(monkeypatch):
    import scripts.replay_validation as _replay
    from pathlib import Path as _P
    live = _P("C:/Users/sind02/Desktop/valyuchain/robo-advisor/data/forward_test.db")
    demo = _P("C:/Users/sind02/Desktop/valyuchain/robo-advisor/data/forward_demo.db")
    before = (_sha(live), _sha(demo))
    monkeypatch.setenv("APP_PROFILE", "live")
    assert _replay.main() == 0
    assert (_sha(live), _sha(demo)) == before
    assert _P("C:/Users/sind02/Desktop/valyuchain/robo-advisor/data/forward_validation.db").exists()
