"""Scheduler job registry tests: idempotency, locking, failure, dry-run purity."""
import sqlite3

from src.forward import jobs as J


def _db(tmp_path):
    p = tmp_path / "jobs.db"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE t (a TEXT)")
    con.commit()
    con.close()
    return p


def test_claim_complete_then_skipped(tmp_path):
    db = _db(tmp_path)
    jid, d = J.claim_job(None, "daily", "2026-09-14", sqlite_path=db)
    assert (jid, d) == (jid, "run") and jid
    assert J.claim_job(None, "daily", "2026-09-14", sqlite_path=db)[1] == "locked"
    J.complete_job(None, jid, {"n": 1}, sqlite_path=db)
    assert J.claim_job(None, "daily", "2026-09-14", sqlite_path=db) == (None, "skipped")
    rows = J.recent_jobs(None, sqlite_path=db)
    assert {r["status"] for r in rows} == {"success", "skipped"}
    assert any(r["status"] == "success" for r in rows)


def test_fail_and_reclaim(tmp_path):
    db = _db(tmp_path)
    jid, _ = J.claim_job(None, "weekly", "2026-09-11", sqlite_path=db)
    J.fail_job(None, jid, "boom", sqlite_path=db)
    jid2, d2 = J.claim_job(None, "weekly", "2026-09-11", sqlite_path=db)
    assert d2 == "run" and jid2 != jid
    rows = J.recent_jobs(None, sqlite_path=db)
    assert {r["status"] for r in rows} == {"failed", "running"}


def test_daily_dry_run_writes_nothing(tmp_path, monkeypatch):
    import src.forward.run_daily as _rd
    from src.forward.db import connect, init_db
    dbp = tmp_path / "fwd.db"
    con = connect(dbp)
    init_db(con)
    con.close()
    monkeypatch.setattr(_rd, "get_database_path", lambda: dbp)
    before = {t: _count(dbp, t) for t in ("orders", "trades", "nav_daily", "events")}
    assert _rd.main(["--dry-run"]) == 0
    after = {t: _count(dbp, t) for t in ("orders", "trades", "nav_daily", "events")}
    assert before == after


def _count(dbp, table):
    con = sqlite3.connect(dbp)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return -1
    finally:
        con.close()


def test_concurrent_duplicate_claim_blocked(tmp_path):
    import threading
    from src.forward.db import connect, init_db
    db = tmp_path / "conc.db"
    con = connect(db)
    init_db(con)
    con.close()
    results = []

    def worker():
        try:
            results.append(J.claim_job(None, "daily", "2026-09-14", sqlite_path=db))
        except Exception as e:  # noqa: BLE001
            results.append(("error", str(e)))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    runs = [r for r in results if r[1] == "run"]
    assert len(runs) == 1, results
    assert all(r[1] == "locked" for r in results if r not in runs)


def test_double_daily_execution_creates_no_duplicates(tmp_path):
    import pandas as pd
    from src.forward.accounts import record_target, versions_from_cfg
    from src.forward.db import connect, init_db
    from src.forward.execution import create_orders, execute_pending
    from src.forward.ledger import valuate
    from src.forward.participants import add_participant
    from src.forward.prices import upsert_prices
    versions = {"benchmark_version": "V", "theme_universe_version": "T",
                "risk_model_version": "R", "execution_rule_version": "E"}
    dbp = tmp_path / "idem.db"
    con = connect(dbp)
    init_db(con)
    idx = pd.bdate_range("2026-09-01", periods=10)
    panel = pd.DataFrame({"us_equity": 100.0, "cash": 1.0}, index=idx)
    upsert_prices(con, panel, "synthetic")
    pid = add_participant(con, "A", "2026-09-01", "V")
    con.execute("INSERT INTO accounts (account_id, participant_id, account_type, shadow_name,"
                " benchmark_version, inception_date, initial_capital_krw, status, created_at)"
                " VALUES ('A-1', ?, 'core', NULL, 'V', '2026-09-01', 100.0, 'active', 'x')", (pid,))
    record_target(con, "A-1", {"us_equity": 0.0, "cash": 1.0}, "2026-09-01", "core",
                  versions, "V", pid)
    record_target(con, "A-1", {"us_equity": 0.5, "cash": 0.5}, "2026-09-08", "core",
                  versions, "V", pid)
    create_orders(con, "A-1", {"us_equity": 0.5, "cash": 0.5},
                  "2026-09-08T00:00:00+00:00", "2026-09-08", "V", pid)
    for _ in range(2):  # same daily job twice
        execute_pending(con, "A-1", "2026-09-14", 5, "V", pid)
        valuate(con, "A-1", "2026-09-14", versions, 100.0)
    con.commit()
    assert _count(dbp, "trades") == 1
    assert _count(dbp, "nav_daily") == 1
    n1 = con.execute("SELECT nav FROM nav_daily").fetchone()[0]
    valuate(con, "A-1", "2026-09-14", versions, 100.0)
    assert con.execute("SELECT nav FROM nav_daily").fetchone()[0] == n1
