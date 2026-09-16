"""Phase 2.2 inception-correction tests. No network; temp DBs only."""
import pandas as pd

from src.forward.db import connect, init_db
from src.forward.execution import create_orders, execute_pending
from src.forward.ledger import nav_series, valuate
from src.forward.participants import add_participant
from src.forward.preflight import run_checks
from src.forward.prices import upsert_prices
from src.forward.state import (canonical_dates, check_invariants, get_state, set_state_once,
                               live_orders_blocked)
from src.forward.themes import register_themes

VERSIONS = {"benchmark_version": "CORE_V0.3", "theme_universe_version": "THEME_UNIVERSE_V0.1",
            "risk_model_version": "R", "execution_rule_version": "E"}
FMETA = {"run_timestamp": "2026-09-12T00:00:00+00:00", "data_end": "2026-09-11"}
THEMES = {"universe_version": "THEME_UNIVERSE_V0.1", "themes": [
    {"theme_id": "ai", "display_name": "ai", "theme_type": "theme", "ticker": "T",
     "market": "US", "currency": "USD", "active": True, "valid_from": "2022-01-01",
     "valid_to": None, "universe_version": "THEME_UNIVERSE_V0.1"}]}


def _db(tmp_path, name="t.db"):
    con = connect(tmp_path / name)
    init_db(con)
    register_themes(con, THEMES)
    return con


def test1_clean_prelaunch_state(tmp_path):
    con = _db(tmp_path)
    assert get_state(con, "forward_test_inception_at") is None
    assert get_state(con, "first_execution_at") is None


def test2_preflight_passes_with_null_inception(tmp_path):
    con = _db(tmp_path)
    idx = pd.bdate_range("2026-09-01", periods=10)
    upsert_prices(con, pd.DataFrame({"us_equity": 100.0}, index=idx), "synthetic")
    import src.forward.preflight as _p
    import types
    cfg = {"forward_test": {"benchmark_version": "CORE_V0.3",
                            "theme_universe_version": "THEME_UNIVERSE_V0.1",
                            "stale_price_days": 365},
           "frozen_dir": "outputs/frozen/CORE_V0.3"}
    ok, lines, _ = run_checks(con, cfg)
    assert ok, lines
    assert get_state(con, "forward_test_inception_at") is None


def test3_init_does_not_launch(tmp_path, monkeypatch):
    import src.forward.init_forward_test as _init
    dbp = tmp_path / "init.db"
    monkeypatch.setattr(_init, "get_database_path", lambda: dbp)
    monkeypatch.setattr(_init, "bootstrap_from_snapshot",
                        lambda con, *a, **k: {"rows": 0, "assets": [], "start": "-", "end": "-"})
    assert _init.main() == 0
    con = connect(dbp)
    assert get_state(con, "forward_test_inception_at") is None
    assert get_state(con, "first_execution_at") is None
    assert con.execute("SELECT COUNT(*) c FROM events WHERE event_type LIKE '%INCEPTION_SET%'"
                       ).fetchone()["c"] == 0


def _launch_cfg():
    return {"forward_test": {"benchmark_version": "CORE_V0.3",
                             "theme_universe_version": "THEME_UNIVERSE_V0.1",
                             "stale_price_days": 365},
            "frozen_dir": "outputs/frozen/CORE_V0.3"}


def test4_launch_sets_inception(tmp_path, monkeypatch):
    import src.forward.launch as _launch
    dbp = tmp_path / "l.db"
    con = _db(tmp_path, "l.db")
    idx = pd.bdate_range("2026-09-01", periods=10)
    upsert_prices(con, pd.DataFrame({"us_equity": 100.0}, index=idx), "synthetic")
    con.commit()
    monkeypatch.setattr(_launch, "get_database_path", lambda: dbp)
    monkeypatch.setenv("APP_PROFILE", "live")
    assert _launch.main() == 0
    inc = get_state(connect(dbp), "forward_test_inception_at")
    assert inc is not None and inc[:10] >= "2026-09-12"
    assert "+09:00" in inc


def test5_double_launch_fails(tmp_path, monkeypatch, capsys):
    import src.forward.launch as _launch
    dbp = tmp_path / "l2.db"
    con = _db(tmp_path, "l2.db")
    idx = pd.bdate_range("2026-09-01", periods=10)
    upsert_prices(con, pd.DataFrame({"us_equity": 100.0}, index=idx), "synthetic")
    con.commit()
    monkeypatch.setattr(_launch, "get_database_path", lambda: dbp)
    monkeypatch.setenv("APP_PROFILE", "live")
    assert _launch.main() == 0
    first = get_state(connect(dbp), "forward_test_inception_at")
    assert _launch.main() == 2
    assert get_state(connect(dbp), "forward_test_inception_at") == first
    assert "already been launched" in capsys.readouterr().out


def _trade_db(tmp_path):
    con = _db(tmp_path, "x.db")
    idx = pd.bdate_range("2026-09-11", periods=5)  # Thu..Wed
    panel = pd.DataFrame({"us_equity": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)
    upsert_prices(con, panel, "synthetic")
    p = add_participant(con, "A", "2026-09-13", "CORE_V0.3")
    con.execute("INSERT INTO accounts (account_id, participant_id, account_type, shadow_name,"
                " benchmark_version, inception_date, initial_capital_krw, status, created_at)"
                " VALUES ('A-X', ?, 'core', NULL, 'CORE_V0.3', '2026-09-13', 100.0, 'active', 'x')",
                (p,))
    from src.forward.accounts import record_target
    record_target(con, "A-X", {"us_equity": 0.0, "cash": 1.0}, "2026-09-10", "core",
                  VERSIONS, "CORE_V0.3", p)
    return con, p


def test6_no_retroactive_execution(tmp_path):
    from src.forward.state import set_state_once
    con, p = _trade_db(tmp_path)
    set_state_once(con, "forward_test_inception_at", "2026-09-13T00:00:00+09:00")
    from src.forward.accounts import record_target
    record_target(con, "A-X", {"us_equity": 0.5, "cash": 0.5}, "2026-09-13", "core",
                  VERSIONS, "CORE_V0.3", p)
    # order effective on snapshot date (pre-inception): must never fill
    create_orders(con, "A-X", {"us_equity": 0.5, "cash": 0.5},
                  "2026-09-11T00:00:00+00:00", "2026-09-11", "CORE_V0.3", p)
    execute_pending(con, "A-X", "2026-09-17", 5, "CORE_V0.3", p)
    assert con.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"] == 0
    assert con.execute("SELECT COUNT(*) c FROM events WHERE event_type ="
                       " 'RETROACTIVE_EXECUTION_BLOCKED'").fetchone()["c"] >= 1
    # legitimate post-inception order fills
    create_orders(con, "A-X", {"us_equity": 0.5, "cash": 0.5},
                  "2026-09-13T00:00:00+00:00", "2026-09-14", "CORE_V0.3", p)
    execute_pending(con, "A-X", "2026-09-17", 5, "CORE_V0.3", p)
    got = con.execute("SELECT MIN(execution_at) m FROM trades").fetchone()["m"]
    assert got == "2026-09-14"  # first session on/after effective 9/14 (Mon)


def test7_first_execution_ordering(tmp_path):
    from src.forward.run_daily import latch_first_execution
    con, p = _trade_db(tmp_path)
    set_state_once(con, "forward_test_inception_at", "2026-09-13T00:00:00+09:00")
    from src.forward.accounts import record_target
    record_target(con, "A-X", {"us_equity": 0.5, "cash": 0.5}, "2026-09-13", "core",
                  VERSIONS, "CORE_V0.3", p)
    create_orders(con, "A-X", {"us_equity": 0.5, "cash": 0.5},
                  "2026-09-13T00:00:00+00:00", "2026-09-14", "CORE_V0.3", p)
    execute_pending(con, "A-X", "2026-09-17", 5, "CORE_V0.3", p)
    first = latch_first_execution(con, "CORE_V0.3")
    assert first is not None and first >= "2026-09-13"
    # never overwritten
    execute_pending(con, "A-X", "2026-09-17", 5, "CORE_V0.3", p)
    assert latch_first_execution(con, "CORE_V0.3") == first


def test8_no_nav_before_execution(tmp_path):
    con, p = _trade_db(tmp_path)
    con.execute("INSERT INTO accounts (account_id, participant_id, account_type, shadow_name,"
                " benchmark_version, inception_date, initial_capital_krw, status, created_at)"
                " VALUES ('A-Y', ?, 'core', NULL, 'CORE_V0.3', '2026-09-13', 100.0, 'active', 'x')",
                (p,))
    r = valuate(con, "A-Y", "2026-09-17", VERSIONS, 100.0)
    assert r["status"] == "NAV_INCOMPLETE"
    assert con.execute("SELECT COUNT(*) c FROM nav_daily WHERE account_id='A-Y'").fetchone()["c"] == 0


def test9_nav_anchor_after_first_execution(tmp_path):
    con, p = _trade_db(tmp_path)
    from src.forward.accounts import record_target
    record_target(con, "A-X", {"us_equity": 0.5, "cash": 0.5}, "2026-09-13", "core",
                  VERSIONS, "CORE_V0.3", p)
    create_orders(con, "A-X", {"us_equity": 0.5, "cash": 0.5},
                  "2026-09-13T00:00:00+00:00", "2026-09-14", "CORE_V0.3", p)
    execute_pending(con, "A-X", "2026-09-17", 5, "CORE_V0.3", p)
    r = valuate(con, "A-X", "2026-09-15", VERSIONS, 100.0)
    assert r["status"] == "OK"
    nav = nav_series(con, "A-X")
    assert nav[0]["nav_base100"] == 100.0


def test10_shadows_and_late_join(tmp_path):
    con = _db(tmp_path)
    set_state_once(con, "forward_test_inception_at", "2026-09-13T00:00:00+09:00")
    con.execute("INSERT INTO accounts (account_id, participant_id, account_type, shadow_name,"
                " benchmark_version, inception_date, initial_capital_krw, status, created_at)"
                " VALUES ('A-SHADOW-core_v03', NULL, 'shadow', 'core_v03', 'CORE_V0.3',"
                " '2026-09-11', 100.0, 'active', 'x')")
    r = valuate(con, "A-SHADOW-core_v03", "2026-09-17", VERSIONS, 100.0)
    assert r["status"] == "NAV_INCOMPLETE"  # same inception rule, no trades yet
    p = add_participant(con, "Late", "2026-09-20", "CORE_V0.3")
    assert get_state(con, "forward_test_inception_at") == "2026-09-13T00:00:00+09:00"


def test_invariants_and_canonical_dates(tmp_path):
    con = _db(tmp_path)
    d = canonical_dates(con, FMETA)
    assert (d["benchmark_model_date"], d["benchmark_snapshot_date"],
            d["forward_test_inception_at"], d["first_execution_at"]) == \
        ("2026-09-12", "2026-09-11", None, None)
    assert check_invariants(d) == []
    assert check_invariants({**d, "forward_test_inception_at": "2026-09-10T00:00:00+09:00"})
    assert check_invariants({**d, "forward_test_inception_at": "2026-09-13T00:00:00+09:00",
                             "first_execution_at": "2026-09-12"}) != []
